"""Resolve NBA player positions for season ingest (stats API has no position column)."""

from __future__ import annotations

import time

import pandas as pd

from src.sports.nba.positions import normalize_nba_position


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


def _positions_from_player_index(season: str) -> dict[str, str]:
    from nba_api.stats.endpoints import playerindex

    resp = playerindex.PlayerIndex(season=season, league_id="00")
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

    teams_resp = leaguedashteamstats.LeagueDashTeamStats(
        season=season,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )
    time.sleep(0.6)
    teams = teams_resp.get_data_frames()[0]
    if teams.empty or "TEAM_ID" not in teams.columns:
        return {}

    mapping: dict[str, str] = {}
    for tid in sorted(teams["TEAM_ID"].dropna().unique()):
        roster_resp = commonteamroster.CommonTeamRoster(
            team_id=int(tid),
            season=season,
        )
        time.sleep(0.6)
        roster = roster_resp.get_data_frames()[0]
        if roster.empty or "PLAYER_ID" not in roster.columns or "POSITION" not in roster.columns:
            continue
        for _, row in roster.iterrows():
            raw_pos = row["POSITION"]
            if pd.isna(raw_pos) or not str(raw_pos).strip():
                continue
            norm = normalize_nba_position(raw_pos)
            if not norm:
                continue
            pid = normalize_player_id(row["PLAYER_ID"])
            if pid:
                mapping[pid] = norm
    return mapping


def fetch_season_positions(end_year: int, *, use_rosters: bool = True) -> dict[str, str]:
    """
    Map player_id -> fantasy position (PG–C).

    Team rosters are the most reliable source; PlayerIndex fills gaps.
    """
    season = _season_str(end_year)
    roster_map = _positions_from_team_rosters(season) if use_rosters else {}
    index_map = _positions_from_player_index(season)

    merged = dict(index_map)
    merged.update(roster_map)
    return merged
