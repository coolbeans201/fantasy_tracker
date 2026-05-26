"""Shared Player Profile layout for MLB / NBA / NHL."""

from __future__ import annotations

import streamlit as st

from app.components import get_db, query_param_season, render_sidebar
from app.sport_context import init_sport_page
from app.sport_profile_entry import player_id_from_profile_link
from app.sport_season_scope import (
    profile_season_scope_caption,
    sync_profile_sidebar_seasons,
)
from src.db.connection import db_exists
from src.sports.player_seasons import player_seasons_available, stats_table
from src.stats_columns import format_stats_dataframe_for_display
from src.ui_text import page_title_suffix, section_h3, title_case_ui


def render_sport_profile_page(sport_id: str, *, label: str) -> None:
    st.set_page_config(page_title=page_title_suffix(f"{label} Player Profile"), layout="wide")
    init_sport_page(sport_id)

    query_season = query_param_season()
    controls = render_sidebar(
        sport=sport_id,
        default_season=st.session_state.get(f"profile_season_default_{sport_id}")
        or query_season,
        season_options=st.session_state.get(f"profile_entity_seasons_{sport_id}"),
        season_scope_caption=profile_season_scope_caption(
            st.session_state.get(f"profile_entity_seasons_{sport_id}")
        ),
    )
    st.title(title_case_ui("Player Profile"))

    if not db_exists() or not controls["seasons"]:
        st.info(f"Ingest {label} data first.")
        st.stop()

    conn = get_db()
    table = stats_table(sport_id)
    player_id, _picked_season, display_name = player_id_from_profile_link(
        conn,
        stats_table=table,
        search_players=_search_fn(sport_id),
        sidebar_season=controls.get("season"),
    )

    available = player_seasons_available(conn, sport_id, player_id)
    sync_profile_sidebar_seasons(sport_id, player_id, available, query_season)

    season = int(controls["season"]) if controls.get("season") is not None else max(available)
    st.subheader(display_name)

    df = conn.execute(
        f"SELECT * FROM {table} WHERE player_id = ? AND season = ?",
        [player_id, season],
    ).df()
    if df.empty:
        st.warning(f"No row for season {season}.")
    else:
        st.markdown(section_h3(f"Season stats ({season})"))
        shown = format_stats_dataframe_for_display(df)
        st.dataframe(shown, use_container_width=True, hide_index=True)
        st.download_button(
            title_case_ui("Download season CSV"),
            shown.to_csv(index=False),
            file_name=f"{sport_id}_profile_{player_id}_{season}.csv",
            mime="text/csv",
        )


def _search_fn(sport_id: str):
    if sport_id == "mlb":
        from src.sports.mlb.queries import search_players

        return search_players
    if sport_id == "nba":
        from src.sports.nba.queries import search_players

        return search_players
    from src.sports.nhl.queries import search_players

    return search_players
