"""Generic season leaders page for MLB / NBA / NHL."""

from __future__ import annotations

import streamlit as st

from app.components import get_db, render_sidebar
from app.leader_navigation import render_leaders_table
from src.analytics.metrics import add_fp_per_game
from src.db.connection import db_exists
from src.sports.registry import get_sport, season_leaders
from src.stats_columns import rename_stats_for_display
from src.ui_text import page_title_suffix, title_case_ui


def render_sport_leaders_page(sport_id: str) -> None:
    meta = get_sport(sport_id)
    st.set_page_config(
        page_title=page_title_suffix(f"{meta.label} Season Leaders"),
        layout="wide",
    )
    from app.sport_context import init_sport_page

    init_sport_page(sport_id)
    controls = render_sidebar(sport=sport_id)
    st.title(title_case_ui("Season Leaders"))

    if not db_exists() or not controls["seasons"]:
        st.info(f"Ingest at least one {meta.label} season to use this page.")
        st.stop()

    conn = get_db()
    season = controls["season"]
    if season is None:
        st.stop()

    positions = st.multiselect(
        title_case_ui("Position"),
        controls["fantasy_positions"],
        default=controls["fantasy_positions"][:1],
    )

    df = season_leaders(
        conn,
        sport_id,
        season,
        controls["preset_key"],
        positions=positions,
        min_games=controls["min_games"],
    )
    if df.empty:
        st.warning("No results for these filters.")
        st.stop()

    df = add_fp_per_game(df)
    display = [
        c
        for c in (
            "player_name",
            "position",
            "team",
            "games",
            "fantasy_points",
            "fp_per_game",
        )
        if c in df.columns
    ]
    name_col = title_case_ui("Player")
    table_df = df.reset_index(drop=True)
    if "player_id" in table_df.columns and season is not None:
        shown = rename_stats_for_display(table_df[display])
        render_leaders_table(
            shown,
            entity_ids=table_df["player_id"],
            display_names=table_df["player_name"],
            season=int(season),
            name_column=name_col,
            sport_id=sport_id,
        )
    else:
        st.dataframe(
            rename_stats_for_display(table_df[display]),
            use_container_width=True,
            hide_index=True,
        )
    st.download_button(
        title_case_ui("Download CSV"),
        rename_stats_for_display(df).to_csv(index=False),
        file_name=f"{sport_id}_leaders_{season}.csv",
        mime="text/csv",
    )
