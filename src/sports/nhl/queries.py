"""NHL query helpers."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.sports.nhl.positions import (
    LEADER_POSITIONS,
    coerce_leader_selection,
    expand_leader_positions,
)
from src.sports.player_search import search_players_table


def _fetch(conn: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> pd.DataFrame:
    if params:
        df = conn.execute(sql, params).df()
    else:
        df = conn.execute(sql).df()
    if len(df.columns):
        df.columns = [str(c).lower() for c in df.columns]
    return df


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
            player_id, player_name, position, team, season, games,
            fantasy_points_espn AS fantasy_points,
            goals, assists, points, shots, hits, blocks,
            wins, saves, goals_against, shutouts
        FROM nhl_player_season_stats
        WHERE season = ?
    """
    params: list = [season]
    if expanded and len(expanded) < len(LEADER_POSITIONS):
        placeholders = ", ".join("?" * len(expanded))
        query += f" AND position IN ({placeholders})"
        params.extend(expanded)
    if min_games and min_games > 0:
        query += " AND games >= ?"
        params.append(min_games)
    if team and str(team).strip() and str(team).strip().upper() != "ALL":
        query += " AND team = ?"
        params.append(str(team).strip())
    query += " ORDER BY fantasy_points_espn DESC NULLS LAST"
    return _fetch(conn, query, params)


def search_players(conn: duckdb.DuckDBPyConnection, query: str = "", limit: int = 200) -> pd.DataFrame:
    return search_players_table(
        conn,
        "nhl_player_season_stats",
        query,
        limit=limit,
        qualify=(
            "ROW_NUMBER() OVER ("
            "PARTITION BY player_id "
            "ORDER BY season DESC, fantasy_points_espn DESC NULLS LAST"
            ") = 1"
        ),
    )
