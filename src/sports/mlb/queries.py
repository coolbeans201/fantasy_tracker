"""MLB query helpers."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.analytics.variance import load_thresholds
from src.sports.mlb.positions import (
    LEADER_POSITIONS,
    coerce_leader_selection,
    expand_leader_positions,
    is_pitcher_only_selection,
)
from src.sports.player_search import search_players_table
from src.text_encoding import normalize_unicode_series


def _fetch(conn: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> pd.DataFrame:
    if params:
        df = conn.execute(sql, params).df()
    else:
        df = conn.execute(sql).df()
    if len(df.columns):
        df.columns = [str(c).lower() for c in df.columns]
    if "player_name" in df.columns:
        df["player_name"] = normalize_unicode_series(df["player_name"])
    return df


def _pitcher_ip_thresholds() -> tuple[float, float]:
    """(SP threshold, RP threshold) from thresholds.yaml with sane fallbacks."""
    gates = (load_thresholds().get("volume_gates_by_sport") or {}).get("mlb", {})
    sp_gate = gates.get("SP", {}) or {}
    rp_gate = gates.get("RP", {}) or {}
    sp = float(sp_gate.get("innings_pitched", 50))
    rp = float(rp_gate.get("innings_pitched", 20))
    return sp, rp


def season_leaders(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    preset_key: str,
    *,
    positions: list[str] | None = None,
    min_games: int | None = None,
    team: str | None = None,
) -> pd.DataFrame:
    del preset_key
    selected = coerce_leader_selection(positions)
    expanded = expand_leader_positions(selected)
    query = """
        SELECT
            player_id,
            player_name,
            position,
            team,
            season,
            games,
            plate_appearances,
            fantasy_points_espn AS fantasy_points,
            runs, home_runs, rbi, stolen_bases,
            wins, strikeouts_pitch, saves, innings_pitched, era
        FROM mlb_player_season_stats
        WHERE season = ?
    """
    params: list = [season]
    if expanded and len(expanded) < len(LEADER_POSITIONS):
        placeholders = ", ".join("?" * len(expanded))
        query += f" AND position IN ({placeholders})"
        params.extend(expanded)
    if min_games and min_games > 0:
        if is_pitcher_only_selection(selected):
            sp_ip, rp_ip = _pitcher_ip_thresholds()
            query += (
                " AND ((position = 'SP' AND innings_pitched >= ?) "
                "OR (position = 'RP' AND innings_pitched >= ?))"
            )
            params.extend([sp_ip, rp_ip])
        else:
            query += " AND plate_appearances >= ?"
            params.append(min_games)
    if team and str(team).strip() and str(team).strip().upper() != "ALL":
        query += " AND team = ?"
        params.append(str(team).strip())
    query += " ORDER BY fantasy_points_espn DESC NULLS LAST"
    return _fetch(conn, query, params)


def search_players(conn: duckdb.DuckDBPyConnection, query: str = "", limit: int = 200) -> pd.DataFrame:
    return search_players_table(
        conn,
        "mlb_player_season_stats",
        query,
        limit=limit,
        qualify=(
            "ROW_NUMBER() OVER ("
            "PARTITION BY player_id "
            "ORDER BY season DESC, fantasy_points_espn DESC NULLS LAST"
            ") = 1"
        ),
    )
