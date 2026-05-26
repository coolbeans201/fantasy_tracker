"""Shared Compare layout for MLB / NBA / NHL with career-scoped sidebar seasons."""

from __future__ import annotations

from collections.abc import Callable

import duckdb
import pandas as pd
import streamlit as st

from app.components import get_db, render_sidebar
from app.sport_context import init_sport_page
from app.sport_season_scope import compare_season_scope_caption, sync_compare_sidebar_seasons
from src.db.connection import db_exists
from src.sports.player_seasons import (
    compare_shared_seasons,
    compare_union_seasons,
    stats_table,
)
from src.ui_text import page_title_suffix, title_case_ui

RowLoader = Callable[[duckdb.DuckDBPyConnection, int], pd.DataFrame]


def render_sport_compare_page(
    sport_id: str,
    *,
    label: str,
    caption: str | None = None,
    load_rows: RowLoader | None = None,
) -> None:
    st.set_page_config(page_title=page_title_suffix(f"{label} Compare"), layout="wide")
    init_sport_page(sport_id)

    controls = render_sidebar(
        sport=sport_id,
        default_season=st.session_state.get(f"compare_season_default_{sport_id}"),
        season_options=st.session_state.get(f"compare_sidebar_seasons_{sport_id}"),
        season_scope_caption=compare_season_scope_caption(
            st.session_state.get(f"compare_sidebar_seasons_{sport_id}"),
            shared_seasons=st.session_state.get(f"compare_shared_seasons_{sport_id}"),
        ),
    )
    st.title(title_case_ui("Compare Players"))
    if caption:
        st.caption(caption)

    if not db_exists() or not controls["seasons"]:
        st.info(f"Ingest {label} data first.")
        st.stop()

    conn = get_db()
    season = int(controls["season"])

    if load_rows is not None:
        rows = load_rows(conn, season)
    else:
        rows = _default_rows(conn, sport_id, season)

    if rows.empty:
        st.warning("No players for this season and filter.")
        st.stop()

    if "player_id" not in rows.columns:
        st.error("Compare row loader must include player_id.")
        st.stop()

    names = rows["player_name"].tolist()
    id_by_name = dict(zip(rows["player_name"], rows["player_id"].astype(str)))

    col1, col2 = st.columns(2)
    with col1:
        name_a = st.selectbox(title_case_ui("Player A"), names, key=f"compare_a_{sport_id}")
    with col2:
        name_b = st.selectbox(title_case_ui("Player B"), names, key=f"compare_b_{sport_id}")

    player_a = id_by_name[name_a]
    player_b = id_by_name[name_b]

    shared = compare_shared_seasons(conn, sport_id, player_a, player_b)
    union = compare_union_seasons(conn, sport_id, player_a, player_b)
    sync_compare_sidebar_seasons(
        sport_id, player_a, player_b, union, shared_seasons=shared
    )

    if not union:
        st.warning("Neither player has season data in the database.")
        st.stop()

    if season not in shared:
        if shared:
            span = f"{shared[-1]}–{shared[0]}"
            st.info(
                f"**{season}** is not a year both players have data. "
                f"Overlapping seasons: **{span}** ({len(shared)} years). "
                "Sidebar lists every year either player appears."
            )
        else:
            st.info(
                "These players have no seasons in common in the database. "
                "Sidebar lists every year either player appears."
            )

    table = stats_table(sport_id)
    ra = conn.execute(
        f"SELECT * FROM {table} WHERE player_id = ? AND season = ?",
        [player_a, season],
    ).df()
    rb = conn.execute(
        f"SELECT * FROM {table} WHERE player_id = ? AND season = ?",
        [player_b, season],
    ).df()

    if ra.empty:
        st.warning(f"No {name_a} row for season {season}.")
    if rb.empty:
        st.warning(f"No {name_b} row for season {season}.")

    if not ra.empty and not rb.empty:
        fp_a = float(ra["fantasy_points_espn"].iloc[0])
        fp_b = float(rb["fantasy_points_espn"].iloc[0])
        c1, c2, c3 = st.columns(3)
        c1.metric(name_a, f"{fp_a:.1f} FP")
        c2.metric(name_b, f"{fp_b:.1f} FP")
        c3.metric(title_case_ui("Difference"), f"{fp_a - fp_b:+.1f}")


def _default_rows(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
) -> pd.DataFrame:
    table = stats_table(sport_id)
    return conn.execute(
        f"""
        SELECT player_id, player_name, position, team,
               fantasy_points_espn AS fantasy_points, games
        FROM {table}
        WHERE season = ?
        ORDER BY fantasy_points_espn DESC
        LIMIT 500
        """,
        [season],
    ).df()
