"""Per-game stat rows for sport profiles."""

from __future__ import annotations

import duckdb
import pandas as pd

GAME_TABLES: dict[str, str] = {
    "nba": "nba_player_game_stats",
    "nhl": "nhl_player_game_stats",
    "mlb": "mlb_player_game_stats",
}


def _table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE lower(table_name) = lower(?)
            LIMIT 1
            """,
            [table],
        ).fetchone()
        return row is not None
    except duckdb.Error:
        return False


def load_player_game_log(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    player_id: str,
    season: int,
) -> pd.DataFrame | None:
    """Return game log for one player-season, or None if table not present."""
    table = GAME_TABLES.get(str(sport_id).strip().lower())
    if not table or not _table_exists(conn, table):
        return None
    df = conn.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE player_id = ? AND season = ?
        ORDER BY game_date NULLS LAST, game_index NULLS LAST
        """,
        [str(player_id).strip(), int(season)],
    ).df()
    if df.empty:
        return df
    df.columns = [str(c).lower() for c in df.columns]
    if "fantasy_points_espn" in df.columns and "fantasy_points" not in df.columns:
        df["fantasy_points"] = df["fantasy_points_espn"]
    return df
