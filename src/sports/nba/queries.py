"""NBA query helpers."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.sports.nba.positions import coerce_leader_selection


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
    query = """
        SELECT
            player_id, player_name, position, team, season, games,
            fantasy_points_espn AS fantasy_points,
            points, rebounds, assists, steals, blocks, turnovers, three_pointers
        FROM nba_player_season_stats
        WHERE season = ?
    """
    params: list = [season]
    if selected and len(selected) < 5:
        placeholders = ",".join(["?"] * len(selected))
        query += f" AND position IN ({placeholders})"
        params.extend(selected)
    if min_games and min_games > 0:
        query += " AND games >= ?"
        params.append(min_games)
    if team and str(team).strip() and str(team).strip().upper() != "ALL":
        query += " AND team = ?"
        params.append(str(team).strip())
    query += " ORDER BY fantasy_points_espn DESC NULLS LAST"
    return _fetch(conn, query, params)


def search_players(conn: duckdb.DuckDBPyConnection, query: str = "", limit: int = 200) -> pd.DataFrame:
    if query.strip():
        return _fetch(
            conn,
            """
            SELECT player_id, player_name, position, season AS last_season
            FROM nba_player_season_stats
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
        FROM nba_player_season_stats
        QUALIFY ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY season DESC) = 1
        ORDER BY last_season DESC, player_name
        LIMIT ?
        """,
        [limit],
    )
