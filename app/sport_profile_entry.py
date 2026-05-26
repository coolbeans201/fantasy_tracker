"""Open sport profile pages from ?entity= & ?season= query params (Leaders links)."""

from __future__ import annotations

import duckdb
import streamlit as st

from app.components import query_param_entity, query_param_season
from src.ui_text import title_case_ui


def player_id_from_profile_link(
    conn: duckdb.DuckDBPyConnection,
    *,
    stats_table: str,
    search_players,
    sidebar_season: int | None = None,
) -> tuple[str, int, str]:
    """
    Resolve player from Leaders link or search UI.

    Returns (player_id, season, display_name).
    """
    link_entity = query_param_entity()
    link_season = query_param_season()

    if link_entity:
        player_id = str(link_entity).strip()
        if link_season is not None:
            st.caption(f"Loaded from Season Leaders: **{link_season}** (`{player_id}`)")
        else:
            st.caption(f"Loaded from link: `{player_id}`")
        if st.button(
            title_case_ui("Clear profile link"),
            key=f"clear_profile_link_{stats_table}",
        ):
            st.query_params.clear()
            st.rerun()
        row = conn.execute(
            f"""
            SELECT player_name FROM {stats_table}
            WHERE player_id = ?
            ORDER BY season DESC
            LIMIT 1
            """,
            [player_id],
        ).fetchone()
        name = str(row[0]) if row else player_id
        season = int(link_season) if link_season is not None else _default_season(conn, stats_table)
        return player_id, season, name

    q = st.text_input(title_case_ui("Search player"), "", key=f"profile_search_{stats_table}")
    limit = 50 if q.strip() else 30
    players = search_players(conn, q, limit=limit)
    if players.empty:
        st.warning("No players found.")
        st.stop()
    pick = st.selectbox(
        title_case_ui("Player"),
        players["player_name"].tolist(),
        key=f"profile_pick_{stats_table}",
    )
    row = players[players["player_name"] == pick].iloc[0]
    if sidebar_season is not None:
        season = int(sidebar_season)
    else:
        season = int(row.get("last_season") or _default_season(conn, stats_table))
    return str(row["player_id"]), season, str(pick)


def _default_season(conn: duckdb.DuckDBPyConnection, stats_table: str) -> int:
    latest = conn.execute(f"SELECT MAX(season) FROM {stats_table}").fetchone()
    if latest and latest[0] is not None:
        return int(latest[0])
    st.warning("No seasons ingested.")
    st.stop()
