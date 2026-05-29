"""Resolve NBA player positions for season ingest (stats API has no position column)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from src.sports.nba.positions import normalize_nba_position

NBA_API_RETRIES = 4
NBA_API_BASE_DELAY_SEC = 1.0


def normalize_player_id(value) -> str:
    """Stable string ID for joins (LeagueDash PLAYER_ID vs roster PLAYER_ID)."""
    num = pd.to_numeric(value, errors="coerce")
    if pd.notna(num):
        return str(int(num))
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _season_str(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _with_retry(fn, *, label: str):
    last: Exception | None = None
    for attempt in range(1, NBA_API_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:  # nba_api can bubble json decode / HTTP failures
            last = exc
            if attempt >= NBA_API_RETRIES:
                break
            wait = NBA_API_BASE_DELAY_SEC * attempt
            print(f"  NBA {label} request failed ({exc}); retrying in {wait:.1f}s...")
            time.sleep(wait)
    assert last is not None
    raise last


def _positions_from_player_index(season: str) -> dict[str, str]:
    from nba_api.stats.endpoints import playerindex

    resp = _with_retry(
        lambda: playerindex.PlayerIndex(season=season, league_id="00"),
        label=f"PlayerIndex {season}",
    )
    time.sleep(0.6)
    idx = resp.get_data_frames()[0]
    if idx.empty:
        return {}

    id_col = "PERSON_ID" if "PERSON_ID" in idx.columns else "PLAYER_ID"
    pos_col = next(
        (
            c
            for c in ("POSITION", "PLAYER_POSITION", "PLAYER_POSITION_ABBREVIATION")
            if c in idx.columns
        ),
        None,
    )
    if pos_col is None:
        return {}

    mapping: dict[str, str] = {}
    for _, row in idx.iterrows():
        raw_pos = row[pos_col]
        if pd.isna(raw_pos) or not str(raw_pos).strip():
            continue
        norm = normalize_nba_position(raw_pos)
        if not norm:
            continue
        pid = normalize_player_id(row[id_col])
        if pid and pid not in mapping:
            mapping[pid] = norm
    return mapping


def _positions_from_team_rosters(season: str) -> dict[str, str]:
    """Season rosters list primary position (PG/SG/SF/PF/C) per player."""
    from nba_api.stats.endpoints import commonteamroster, leaguedashteamstats

    teams_resp = _with_retry(
        lambda: leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            season_type_all_star="Regular Season",
            per_mode_detailed="PerGame",
        ),
        label=f"LeagueDashTeamStats {season}",
    )
    time.sleep(0.6)
    teams = teams_resp.get_data_frames()[0]
    if teams.empty or "TEAM_ID" not in teams.columns:
        return {}

    mapping: dict[str, str] = {}
    for tid in sorted(teams["TEAM_ID"].dropna().unique()):
        roster_resp = _with_retry(
            lambda tid=tid: commonteamroster.CommonTeamRoster(
                team_id=int(tid),
                season=season,
            ),
            label=f"CommonTeamRoster {season} team={int(tid)}",
        )
        time.sleep(0.6)
        roster = roster_resp.get_data_frames()[0]
        if roster.empty or "PLAYER_ID" not in roster.columns or "POSITION" not in roster.columns:
            continue
        for _, row in roster.iterrows():
            raw_pos = row["POSITION"]
            if pd.isna(raw_pos) or not str(raw_pos).strip():
                continue
            # Skip coarse guard labels that normalize to None; F / F-C map to PF.
            raw_key = str(raw_pos).strip().upper().replace(" ", "")
            if raw_key in {"G", "GUARD", "GF", "FG", "CF"}:
                continue
            norm = normalize_nba_position(raw_pos)
            if not norm:
                continue
            pid = normalize_player_id(row["PLAYER_ID"])
            if pid:
                mapping[pid] = norm
    return mapping


def _default_nba_cache_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "cache" / "nba"


def _positions_cache_path(end_year: int, *, use_rosters: bool, cache_dir: Path) -> Path:
    suffix = "_rosters" if use_rosters else ""
    return cache_dir / f"positions_{end_year}{suffix}.json"


def _load_positions_cache(path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(raw, dict):
        return None
    out: dict[str, str] = {}
    for k, v in raw.items():
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        ks, vs = str(k).strip(), str(v).strip()
        if ks and vs:
            out[ks] = vs
    return out


def _save_positions_cache(path: Path, positions: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(sorted(positions.items())), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def fetch_season_positions(
    end_year: int,
    *,
    use_rosters: bool = True,
    refresh_positions: bool = False,
    cache_dir: Path | None = None,
) -> dict[str, str]:
    """
    Map player_id -> fantasy position (PG–C).

    Team rosters provide the most reliable primary position labels (PG/SG/SF/PF/C)
    and are enabled by default; PlayerIndex fills remaining gaps.
    Results are written under ``data/cache/nba/`` (gitignored) keyed by season and
    ``use_rosters``. Pass ``refresh_positions=True`` to ignore the cache and
    overwrite it after a fresh fetch.
    """
    resolved_cache = cache_dir if cache_dir is not None else _default_nba_cache_dir()
    cache_path = _positions_cache_path(end_year, use_rosters=use_rosters, cache_dir=resolved_cache)

    if not refresh_positions:
        cached = _load_positions_cache(cache_path)
        # Empty dict means missing/invalid cache — do not skip the API.
        if cached:
            return cached

    season = _season_str(end_year)
    roster_map = _positions_from_team_rosters(season) if use_rosters else {}
    index_map = _positions_from_player_index(season)

    merged = dict(index_map)
    merged.update(roster_map)
    _save_positions_cache(cache_path, merged)
    return merged
