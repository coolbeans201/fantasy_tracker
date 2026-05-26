#!/usr/bin/env python3
"""Ingest MLB season stats into DuckDB (Baseball Reference via pybaseball)."""

from __future__ import annotations

import argparse
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
from src.sports.mlb.position_lookup import (  # noqa: E402
    load_field_position_map,
    resolve_field_position,
)
from src.sports.mlb.positions import (  # noqa: E402
    classify_pitcher_role,
    is_pitcher_position,
    normalize_mlb_field_position,
)
from src.sports.mlb.consolidate import consolidate_mlb_season_frame  # noqa: E402
from src.sports.mlb.scoring import compute_hitter_fp, compute_pitcher_fp  # noqa: E402
from src.sports.mlb.teams import normalize_mlb_team  # noqa: E402
from src.text_encoding import normalize_unicode_series  # noqa: E402

# FanGraphs often returns 403; BRef works but is limited to seasons from 2008 onward.
BREF_MIN_SEASON = 2008
BREF_FETCH_ATTEMPTS = 5
BREF_RETRY_BASE_DELAY_SEC = 4.0


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


def _batting_frame_bref(year: int, pos_by_name: dict[str, str]) -> pd.DataFrame:
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
    out["position"] = out["player_name"].map(
        lambda n: resolve_field_position(n, pos_by_name)
    )
    out["team"] = _series(raw, "Tm", "Team", "team").map(normalize_mlb_team)
    out["games"] = games.loc[raw.index].astype(int)
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
    pos_col = "Pos" if "Pos" in raw.columns else None
    out = pd.DataFrame()
    out["player_id"] = raw["IDfg"].astype(str)
    out["player_name"] = normalize_unicode_series(raw["Name"].astype(str))
    out["season"] = year
    if pos_col:
        out["position"] = raw[pos_col].map(normalize_mlb_field_position).fillna("UTIL")
    else:
        pos_by_name = load_field_position_map(year)
        out["position"] = out["player_name"].map(
            lambda n: resolve_field_position(n, pos_by_name)
        )
    out["team"] = raw.get("Team", pd.Series(["UNK"] * len(raw))).map(normalize_mlb_team)
    out["games"] = pd.to_numeric(raw.get("G", 0), errors="coerce").fillna(0).astype(int)
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
    pos_by_name = load_field_position_map(year)

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
        hit = _batting_frame_bref(year, pos_by_name)
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
    p.add_argument("--from-year", type=int, default=2008)
    p.add_argument("--to-year", type=int, default=2025)
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop bulk ingest on first season error (default: skip and continue)",
    )
    args = p.parse_args()

    if args.bulk:
        years = range(args.from_year, args.to_year + 1)
        print(f"Bulk MLB ingest: {args.from_year}–{args.to_year} ({len(years)} seasons, source={args.source})")
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
            delay = 3.0 if args.source == "bref" else 1.5
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
