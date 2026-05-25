"""MLB query helpers."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.sports.mlb.positions import PITCHER_POSITION, coerce_leader_selection
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
    pos = selected[0] if len(selected) == 1 else None
    query = """
        SELECT
            player_id,
            player_name,
            position,
            team,
            season,
            games,
            fantasy_points_espn AS fantasy_points,
            runs, home_runs, rbi, stolen_bases,
            wins, strikeouts_pitch, saves, innings_pitched, era
        FROM mlb_player_season_stats
        WHERE season = ?
    """
    params: list = [season]
    if pos:
        query += " AND position = ?"
        params.append(pos)
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
            FROM mlb_player_season_stats
            WHERE player_name ILIKE ?
            QUALIFY ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY season DESC) = 1
            ORDER BY player_name
            LIMIT ?
            """,
            [f"%{query.strip()}%", limit],
        )
    return _fetch(
        conn,
        """
        SELECT player_id, player_name, position, season AS last_season
        FROM mlb_player_season_stats
        QUALIFY ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY season DESC) = 1
        ORDER BY last_season DESC, player_name
        LIMIT ?
        """,
        [limit],
    )
