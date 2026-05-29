#!/usr/bin/env python3
"""Ingest MLB season stats into DuckDB (Baseball Reference via pybaseball)."""

from __future__ import annotations

import argparse
import functools
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.db.sport_schema import (  # noqa: E402
    MLB_PLAYER_SEASON_COLUMNS,
    ensure_mlb_player_season_stats_schema,
)
from src.sports.mlb.positions import (  # noqa: E402
    DEFAULT_HITTER_POSITION,
    classify_pitcher_role,
    is_pitcher_position,
    normalize_mlb_field_position,
)
from src.sports.mlb.batting_position import batting_positions_series  # noqa: E402
from src.sports.mlb.consolidate import consolidate_mlb_season_frame  # noqa: E402
from src.sports.mlb.regular_season_games import (  # noqa: E402
    _load_team_aliases,
    apply_regular_season_overlay,
    fetch_regular_season_stats_frame,
)
from src.sports.mlb.scoring import compute_hitter_fp, compute_pitcher_fp  # noqa: E402
from src.sports.mlb.teams import normalize_mlb_team  # noqa: E402
from src.text_encoding import normalize_unicode_series  # noqa: E402

# FanGraphs often returns 403; BRef works but is limited to seasons from 2008 onward.
BREF_MIN_SEASON = 2008
BREF_FETCH_ATTEMPTS = 5
BREF_RETRY_BASE_DELAY_SEC = 4.0
DEFAULT_BULK_DELAY_BREF_SEC = 3.0
DEFAULT_BULK_DELAY_OTHER_SEC = 1.5


class BRefScrapeError(RuntimeError):
    """BRef HTML had no stats table (rate limit, blocked page, or transient outage)."""


_BREF_RETRY_EXCEPTIONS = (
    IndexError,
    AttributeError,
    KeyError,
    ValueError,
    requests.exceptions.RequestException,
)


def _fetch_bref_raw(year: int, *, batting: bool) -> pd.DataFrame:
    """Call pybaseball BRef helpers with retries (bulk runs often hit rate limits)."""
    if batting:
        from pybaseball import batting_stats_bref as fetch_fn

        label = "batting"
    else:
        from pybaseball import pitching_stats_bref as fetch_fn

        label = "pitching"

    last: BaseException | None = None
    for attempt in range(1, BREF_FETCH_ATTEMPTS + 1):
        try:
            raw = fetch_fn(year)
            if raw is not None and not raw.empty:
                return raw
            last = BRefScrapeError(f"empty {label} table")
        except _BREF_RETRY_EXCEPTIONS as exc:
            last = exc
        if attempt < BREF_FETCH_ATTEMPTS:
            wait = BREF_RETRY_BASE_DELAY_SEC * attempt
            print(
                f"  BRef {label} {year} failed ({last}); "
                f"retry in {wait:.0f}s ({attempt}/{BREF_FETCH_ATTEMPTS})…"
            )
            time.sleep(wait)
    raise BRefScrapeError(
        f"Baseball Reference {label} stats unavailable for {year} "
        f"after {BREF_FETCH_ATTEMPTS} attempts"
    ) from last


def _parse_seasons_arg(raw: str | None) -> list[int]:
    """Parse --seasons like '2019,2021-2023' into sorted unique years."""
    if not raw:
        return []
    out: set[int] = set()
    for token in str(raw).split(","):
        piece = token.strip()
        if not piece:
            continue
        if "-" in piece:
            lo_s, hi_s = piece.split("-", 1)
            lo = int(lo_s.strip())
            hi = int(hi_s.strip())
            if hi < lo:
                lo, hi = hi, lo
            out.update(range(lo, hi + 1))
        else:
            out.add(int(piece))
    return sorted(out)


def _append_failure_log(path: Path, year: int, source: str, exc: Exception) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{ts}\t{year}\t{source}\t{type(exc).__name__}\t{exc}\n")

def _series(raw: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in raw.columns:
            return raw[name]
    return pd.Series([None] * len(raw), index=raw.index)


def _player_names(raw: pd.DataFrame) -> pd.Series:
    return normalize_unicode_series(_series(raw, "Name", "name").astype(str))


def _player_id(raw: pd.DataFrame) -> pd.Series:
    names = _series(raw, "Name", "name").astype(str).str.strip()
    if "mlbID" in raw.columns:
        ids = raw["mlbID"].astype(str).str.strip()
        bad = ids.isin(("", "nan", "None", "<NA>", "NaN"))
        return ids.where(~bad, names)
    if "IDfg" in raw.columns:
        return raw["IDfg"].astype(str).str.strip()
    return names


@functools.lru_cache(maxsize=32)
def _mlb_primary_position_by_id(season: int) -> dict[str, str]:
    """ID-based MLB primary position mapping from StatsAPI people endpoint."""
    try:
        resp = requests.get(
            "https://statsapi.mlb.com/api/v1/sports/1/players",
            params={"season": int(season)},
            timeout=45,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        return {}
    people = payload.get("people") or []
    if not isinstance(people, list):
        return {}
    out: dict[str, str] = {}
    for p in people:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "").strip()
        if not pid:
            continue
        raw_pos = ((p.get("primaryPosition") or {}).get("abbreviation")) or None
        pos = normalize_mlb_field_position(raw_pos)
        if pos:
            out[pid] = pos
    return out


def _batting_frame_bref(year: int) -> pd.DataFrame:
    raw = _fetch_bref_raw(year, batting=True)
    if raw is None or raw.empty:
        return pd.DataFrame()
    games = pd.to_numeric(_series(raw, "G"), errors="coerce").fillna(0)
    raw = raw[games > 0].copy()
    if raw.empty:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["player_id"] = _player_id(raw)
    out["player_name"] = _player_names(raw)
    out["season"] = year
    pos_by_id = _mlb_primary_position_by_id(year)
    out["position"] = batting_positions_series(
        raw, out["player_id"], api_by_id=pos_by_id
    )
    from src.rankings.fantasypros_positions import overlay_positions_on_frame

    out, _fp_n = overlay_positions_on_frame(out, "mlb")
    out["team"] = _series(raw, "Tm", "Team", "team").map(normalize_mlb_team)
    out["games"] = games.loc[raw.index].astype(int)
    out["plate_appearances"] = pd.to_numeric(_series(raw, "PA"), errors="coerce").fillna(0)
    out["runs"] = pd.to_numeric(_series(raw, "R"), errors="coerce").fillna(0)
    out["home_runs"] = pd.to_numeric(_series(raw, "HR"), errors="coerce").fillna(0)
    out["rbi"] = pd.to_numeric(_series(raw, "RBI"), errors="coerce").fillna(0)
    out["stolen_bases"] = pd.to_numeric(_series(raw, "SB"), errors="coerce").fillna(0)
    out["walks"] = pd.to_numeric(_series(raw, "BB"), errors="coerce").fillna(0)
    out["strikeouts_bat"] = pd.to_numeric(_series(raw, "SO"), errors="coerce").fillna(0)
    out["batting_avg"] = pd.to_numeric(_series(raw, "BA", "AVG"), errors="coerce").fillna(0)
    for c in ("wins", "strikeouts_pitch", "saves", "innings_pitched", "era", "whip"):
        out[c] = 0.0
    out["fantasy_points_espn"] = compute_hitter_fp(out)
    return out[out["player_id"].astype(str).str.len() > 0]


def _pitching_frame_bref(year: int) -> pd.DataFrame:
    raw = _fetch_bref_raw(year, batting=False)
    if raw is None or raw.empty:
        return pd.DataFrame()
    games = pd.to_numeric(_series(raw, "G"), errors="coerce").fillna(0)
    raw = raw[games > 0].copy()
    if raw.empty:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["player_id"] = _player_id(raw)
    out["player_name"] = _player_names(raw)
    out["season"] = year
    g = games.loc[raw.index]
    gs = pd.to_numeric(_series(raw, "GS"), errors="coerce").fillna(0)
    sv = pd.to_numeric(_series(raw, "SV"), errors="coerce").fillna(0)
    out["position"] = pd.DataFrame({"g": g, "gs": gs, "sv": sv}).apply(
        lambda r: classify_pitcher_role(r["g"], r["gs"], r["sv"]),
        axis=1,
    )
    out["team"] = _series(raw, "Tm", "Team", "team").map(normalize_mlb_team)
    out["games"] = games.loc[raw.index].astype(int)
    out["plate_appearances"] = 0.0
    out["wins"] = pd.to_numeric(_series(raw, "W"), errors="coerce").fillna(0)
    out["strikeouts_pitch"] = pd.to_numeric(_series(raw, "SO"), errors="coerce").fillna(0)
    out["saves"] = pd.to_numeric(_series(raw, "SV"), errors="coerce").fillna(0)
    out["innings_pitched"] = pd.to_numeric(_series(raw, "IP"), errors="coerce").fillna(0)
    out["era"] = pd.to_numeric(_series(raw, "ERA"), errors="coerce").fillna(0)
    out["whip"] = pd.to_numeric(_series(raw, "WHIP"), errors="coerce").fillna(0)
    for c in ("runs", "home_runs", "rbi", "stolen_bases", "walks", "strikeouts_bat", "batting_avg"):
        out[c] = 0.0
    out["fantasy_points_espn"] = compute_pitcher_fp(out)
    return out[out["player_id"].astype(str).str.len() > 0]


def _batting_frame_fangraphs(year: int) -> pd.DataFrame:
    from pybaseball import batting_stats

    raw = batting_stats(year, qual=1)
    if raw is None or raw.empty:
        return pd.DataFrame()
    out = pd.DataFrame()
    out["player_id"] = raw["IDfg"].astype(str)
    out["player_name"] = normalize_unicode_series(raw["Name"].astype(str))
    out["season"] = year
    out["position"] = DEFAULT_HITTER_POSITION
    from src.rankings.fantasypros_positions import overlay_positions_on_frame

    out, _fp_n = overlay_positions_on_frame(out, "mlb")
    out["team"] = raw.get("Team", pd.Series(["UNK"] * len(raw))).map(normalize_mlb_team)
    out["games"] = pd.to_numeric(raw.get("G", 0), errors="coerce").fillna(0).astype(int)
    out["plate_appearances"] = pd.to_numeric(raw.get("PA", 0), errors="coerce").fillna(0)
    out["runs"] = pd.to_numeric(raw.get("R", 0), errors="coerce").fillna(0)
    out["home_runs"] = pd.to_numeric(raw.get("HR", 0), errors="coerce").fillna(0)
    out["rbi"] = pd.to_numeric(raw.get("RBI", 0), errors="coerce").fillna(0)
    out["stolen_bases"] = pd.to_numeric(raw.get("SB", 0), errors="coerce").fillna(0)
    out["walks"] = pd.to_numeric(raw.get("BB", 0), errors="coerce").fillna(0)
    out["strikeouts_bat"] = pd.to_numeric(raw.get("SO", 0), errors="coerce").fillna(0)
    out["batting_avg"] = pd.to_numeric(raw.get("AVG", 0), errors="coerce").fillna(0)
    for c in (
        "wins",
        "strikeouts_pitch",
        "saves",
        "innings_pitched",
        "era",
        "whip",
    ):
        out[c] = 0.0
    out["fantasy_points_espn"] = compute_hitter_fp(out)
    return out


def _pitching_frame_fangraphs(year: int) -> pd.DataFrame:
    from pybaseball import pitching_stats

    raw = pitching_stats(year, qual=1)
    if raw is None or raw.empty:
        return pd.DataFrame()
    out = pd.DataFrame()
    out["player_id"] = raw["IDfg"].astype(str)
    out["player_name"] = normalize_unicode_series(raw["Name"].astype(str))
    out["season"] = year
    g = pd.to_numeric(raw.get("G", 0), errors="coerce").fillna(0)
    gs = pd.to_numeric(raw.get("GS", 0), errors="coerce").fillna(0)
    sv = pd.to_numeric(raw.get("SV", 0), errors="coerce").fillna(0)
    out["position"] = pd.DataFrame({"g": g, "gs": gs, "sv": sv}).apply(
        lambda r: classify_pitcher_role(r["g"], r["gs"], r["sv"]),
        axis=1,
    )
    out["team"] = raw.get("Team", pd.Series(["UNK"] * len(raw))).map(normalize_mlb_team)
    out["games"] = g.astype(int)
    out["plate_appearances"] = 0.0
    out["wins"] = pd.to_numeric(raw.get("W", 0), errors="coerce").fillna(0)
    out["strikeouts_pitch"] = pd.to_numeric(raw.get("SO", 0), errors="coerce").fillna(0)
    out["saves"] = pd.to_numeric(raw.get("SV", 0), errors="coerce").fillna(0)
    out["innings_pitched"] = pd.to_numeric(raw.get("IP", 0), errors="coerce").fillna(0)
    out["era"] = pd.to_numeric(raw.get("ERA", 0), errors="coerce").fillna(0)
    out["whip"] = pd.to_numeric(raw.get("WHIP", 0), errors="coerce").fillna(0)
    for c in ("runs", "home_runs", "rbi", "stolen_bases", "walks", "strikeouts_bat", "batting_avg"):
        out[c] = 0.0
    out["fantasy_points_espn"] = compute_pitcher_fp(out)
    return out


def _fetch_frames(year: int, source: str) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    if year < BREF_MIN_SEASON and source in ("auto", "bref"):
        raise ValueError(
            f"Baseball Reference ingest supports seasons {BREF_MIN_SEASON}+. "
            f"Use --source fangraphs for older years (may be blocked)."
        )

    if source == "fangraphs":
        hit = _batting_frame_fangraphs(year)
        time.sleep(0.5)
        pit = _pitching_frame_fangraphs(year)
        return hit, pit, "fangraphs"

    # auto and bref: try BRef first; FanGraphs fallback when BRef has no table
    # (IndexError in pybaseball = empty soup, often rate limits or bot blocks).
    try:
        hit = _batting_frame_bref(year)
        time.sleep(2.0)
        pit = _pitching_frame_bref(year)
        if not hit.empty or not pit.empty:
            return hit, pit, "baseball_reference"
        raise BRefScrapeError(f"No Baseball Reference rows for {year}")
    except (
        BRefScrapeError,
        IndexError,
        requests.exceptions.RequestException,
        ValueError,
    ) as exc:
        hint = (
            " (BRef returned no stats table — wait and retry, or use --source fangraphs only)"
        )
        print(f"  Baseball Reference failed ({exc!r}); trying FanGraphs…{hint}")

    try:
        hit = _batting_frame_fangraphs(year)
        time.sleep(0.5)
        pit = _pitching_frame_fangraphs(year)
        return hit, pit, "fangraphs"
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(
            "Both Baseball Reference and FanGraphs failed. "
            "FanGraphs often returns 403 — wait and retry BRef, or try another network."
        ) from exc


def ingest_season(year: int, *, source: str = "auto") -> None:
    init_schema()
    conn = get_connection()
    ensure_mlb_player_season_stats_schema(conn)
    hit, pit, used = _fetch_frames(year, source)
    try:
        aliases = _load_team_aliases(year)
        hit_overlay = fetch_regular_season_stats_frame(
            year, group="hitting", aliases=aliases
        )
        pit_overlay = fetch_regular_season_stats_frame(
            year, group="pitching", aliases=aliases
        )
        hit = apply_regular_season_overlay(
            hit, hit_overlay, season=year, group="hitting", aliases=aliases
        )
        pit = apply_regular_season_overlay(
            pit, pit_overlay, season=year, group="pitching", aliases=aliases
        )
        print(
            f"  MLB {year}: regular-season counting stats from MLB Stats API "
            f"(gameType=R; BRef totals can include postseason)"
        )
    except Exception as exc:
        print(f"  MLB {year}: games overlay skipped ({exc!r}); using source G column")
    frame = consolidate_mlb_season_frame(pd.concat([hit, pit], ignore_index=True))
    if frame.empty:
        print(f"No MLB data for {year} (source={used}).")
        conn.close()
        return
    conn.execute("DELETE FROM mlb_player_season_stats WHERE season = ?", [year])
    frame = frame[list(MLB_PLAYER_SEASON_COLUMNS)]
    conn.register("_mlb", frame)
    cols = ", ".join(MLB_PLAYER_SEASON_COLUMNS)
    conn.execute(
        f"INSERT INTO mlb_player_season_stats ({cols}) SELECT {cols} FROM _mlb"
    )
    conn.unregister("_mlb")
    conn.execute("DELETE FROM mlb_ingest_manifest WHERE season = ?", [year])
    conn.execute(
        """
        INSERT INTO mlb_ingest_manifest (season, ingested_at, row_count)
        VALUES (?, ?, ?)
        """,
        [year, datetime.now(timezone.utc), len(frame)],
    )
    conn.close()
    print(
        f"Ingested MLB {year} via {used}: {len(hit)} hitters, {len(pit)} pitchers "
        f"({len(frame)} rows)"
    )


def main() -> None:
    global BREF_FETCH_ATTEMPTS, BREF_RETRY_BASE_DELAY_SEC
    p = argparse.ArgumentParser(description="Ingest MLB season into DuckDB")
    p.add_argument("--season", type=int, help="Calendar year (e.g. 2024); not used with --bulk")
    p.add_argument(
        "--source",
        choices=("auto", "bref", "fangraphs"),
        default="auto",
        help=(
            "auto|bref: try Baseball Reference first, then FanGraphs if BRef has no table "
            "(rate limits / blocks). fangraphs: FanGraphs only (may 403)."
        ),
    )
    p.add_argument("--bulk", action="store_true", help="Ingest --from-year through --to-year")
    p.add_argument(
        "--seasons",
        type=str,
        default=None,
        help="Explicit years (comma/range), e.g. 2019,2021-2023; overrides --from-year/--to-year",
    )
    p.add_argument("--from-year", type=int, default=2008)
    p.add_argument("--to-year", type=int, default=2025)
    p.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Delay between bulk seasons in seconds (default: source-based).",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=BREF_FETCH_ATTEMPTS,
        help="BRef retry attempts per batting/pitching call.",
    )
    p.add_argument(
        "--retry-base-delay",
        type=float,
        default=BREF_RETRY_BASE_DELAY_SEC,
        help="Base seconds for linear retry backoff (attempt * base).",
    )
    p.add_argument(
        "--failure-log",
        type=str,
        default="data/ingest_failures_mlb.log",
        help="Append skipped bulk years to this TSV log file.",
    )
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop bulk ingest on first season error (default: skip and continue)",
    )
    args = p.parse_args()
    BREF_FETCH_ATTEMPTS = max(1, int(args.retries))
    BREF_RETRY_BASE_DELAY_SEC = max(0.1, float(args.retry_base_delay))

    if args.bulk:
        explicit_years = _parse_seasons_arg(args.seasons)
        if explicit_years:
            years = explicit_years
            label = ",".join(str(y) for y in years)
        else:
            years = list(range(args.from_year, args.to_year + 1))
            label = f"{args.from_year}–{args.to_year}"
        print(f"Bulk MLB ingest: {label} ({len(years)} seasons, source={args.source})")
        skipped: list[int] = []
        for year in years:
            print(f"--- MLB {year} ---")
            try:
                ingest_season(year, source=args.source)
            except Exception as exc:
                if args.fail_fast:
                    raise
                print(f"  WARNING: skipped MLB {year}: {exc}")
                skipped.append(year)
                _append_failure_log(Path(args.failure_log), year, args.source, exc)
            delay = (
                float(args.delay)
                if args.delay is not None
                else (
                    DEFAULT_BULK_DELAY_BREF_SEC
                    if args.source == "bref"
                    else DEFAULT_BULK_DELAY_OTHER_SEC
                )
            )
            if delay > 0:
                time.sleep(delay)
        if skipped:
            print(f"Skipped {len(skipped)} season(s): {skipped}")
            print("Re-run failed years, e.g. --season 2024 (auto/bref retry BRef then FanGraphs)")
    elif args.season is not None:
        ingest_season(args.season, source=args.source)
    else:
        p.error("Provide --season YEAR or --bulk with --from-year and --to-year")


if __name__ == "__main__":
    main()
