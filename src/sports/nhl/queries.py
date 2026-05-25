"""NHL query helpers."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.sports.nhl.positions import GOALIE_POSITION, SKATER_POSITION, coerce_leader_selection


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
) -> pd.DataFrame:
    del preset_key
    selected = coerce_leader_selection(positions)
    pos = GOALIE_POSITION if selected == [GOALIE_POSITION] else SKATER_POSITION
    query = """
        SELECT
            player_id, player_name, position, team, season, games,
            fantasy_points_espn AS fantasy_points,
            goals, assists, points, shots, hits, blocks,
            wins, saves, goals_against, shutouts
        FROM nhl_player_season_stats
        WHERE season = ? AND position = ?
    """
    params: list = [season, pos]
    if min_games and min_games > 0:
        query += " AND games >= ?"
        params.append(min_games)
    query += " ORDER BY fantasy_points_espn DESC NULLS LAST"
    return _fetch(conn, query, params)


def search_players(conn: duckdb.DuckDBPyConnection, query: str = "", limit: int = 200) -> pd.DataFrame:
    if query.strip():
        return _fetch(
            conn,
            """
            SELECT player_id, player_name, position, season AS last_season
            FROM nhl_player_season_stats
            WHERE player_name ILIKE ?
            QUALIFY ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY season DESC) = 1
            LIMIT ?
            """,
            [f"%{query.strip()}%", limit],
        )
    return _fetch(
        conn,
        """
        SELECT player_id, player_name, position, season AS last_season
        FROM nhl_player_season_stats
        QUALIFY ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY season DESC) = 1
        ORDER BY last_season DESC, player_name
        LIMIT ?
        """,
        [limit],
    )
