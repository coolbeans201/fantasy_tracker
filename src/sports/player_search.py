"""Accent-insensitive player name search across sport season tables."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.text_encoding import fold_for_search, player_name_matches_query


def _fetch(conn: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> pd.DataFrame:
    if params:
        df = conn.execute(sql, params).df()
    else:
        df = conn.execute(sql).df()
    if len(df.columns):
        df.columns = [str(c).lower() for c in df.columns]
    return df


def search_players_table(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    query: str = "",
    *,
    limit: int = 200,
    qualify: str = "ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY season DESC) = 1",
    empty_order: str = "last_season DESC, player_name",
) -> pd.DataFrame:
    """Search distinct players; matches accents when query omits them (Jokic -> Jokić)."""
    if not query.strip():
        return _fetch(
            conn,
            f"""
            SELECT player_id, player_name, position, season AS last_season
            FROM {table}
            QUALIFY {qualify}
            ORDER BY {empty_order}
            LIMIT ?
            """,
            [limit],
        )

    q = query.strip()
    tokens = [t for t in fold_for_search(q).split() if t]
    if not tokens:
        return pd.DataFrame()

    pattern = f"%{tokens[0]}%"
    prefetch = min(max(limit * 15, 300), 2500)
    df = _fetch(
        conn,
        f"""
        SELECT player_id, player_name, position, season AS last_season
        FROM {table}
        WHERE player_name ILIKE ?
        QUALIFY {qualify}
        """,
        [pattern],
    )
    if df.empty and len(tokens) > 1:
        df = _fetch(
            conn,
            f"""
            SELECT player_id, player_name, position, season AS last_season
            FROM {table}
            QUALIFY {qualify}
            """,
        )

    if df.empty:
        return df

    mask = df["player_name"].map(lambda name: player_name_matches_query(name, q))
    df = df[mask]
    if "last_season" in df.columns:
        df = df.sort_values(["last_season", "player_name"], ascending=[False, True])
    return df.head(limit)
