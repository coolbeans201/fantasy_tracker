"""Shared Streamlit UI components."""

from __future__ import annotations

import streamlit as st
from rapidfuzz import fuzz, process

from src.db.connection import (
    db_exists,
    get_connection,
    list_ingested_seasons,
    players_table_needs_rebuild,
    recompute_games_played,
    rebuild_players_table,
    refresh_player_display_names,
)
from src.db.queries import search_fantasy_entities
from src.positions import FANTASY_POSITIONS, leader_position_options
from src.scoring.calc import DISPLAY_PRESETS
from src.settings import get_min_games_default


def render_sidebar() -> dict:
    """Global sidebar controls."""
    st.sidebar.title("Fantasy Tracker")
    st.sidebar.caption("NFL completed-season analytics")

    if not db_exists():
        st.sidebar.warning("No database found. Run ingest first.")
        return {"season": None, "preset": "Half-PPR", "era_z": False, "min_games": get_min_games_default()}

    seasons = list_ingested_seasons()
    if not seasons:
        st.sidebar.warning("No seasons ingested.")
        return {"season": None, "preset": "Half-PPR", "era_z": False, "min_games": get_min_games_default()}

    preset = st.sidebar.selectbox("Scoring", list(DISPLAY_PRESETS.keys()), index=1)
    season = st.sidebar.selectbox("Season", seasons, index=0)
    default_min = get_min_games_default()
    min_games = st.sidebar.slider(
        "Min games played",
        min_value=1,
        max_value=17,
        value=default_min,
        help=f"Default {default_min} (config/settings.yaml) — half-season threshold",
    )
    era_z = st.sidebar.checkbox("Show peer Z (all-time era)", value=False)

    return {
        "season": season,
        "preset": preset,
        "era_z": era_z,
        "min_games": min_games,
        "fantasy_positions": leader_position_options(),
    }


def fuzzy_entity_select(
    label: str,
    conn,
    key: str,
    default_name: str | None = None,
) -> str | None:
    """Fuzzy autocomplete picker. Returns player_id or dst:TEAM for team defenses."""
    search = st.text_input(
        f"Search {label}",
        key=f"{key}_search",
        placeholder="Name or team (e.g. Andrew Luck, Cardinals, DEN)",
    )
    query = search.strip()
    if len(query) < 2:
        st.caption(
            "Type at least 2 characters to search players and team defenses (DST)."
        )
        return None

    entities_df = search_fantasy_entities(conn, query=query, limit=200)
    if entities_df.empty:
        st.warning(f"No players or defenses matching “{query}”.")
        return None

    labels = [
        f"{row.player_name} ({row.position}, last: {row.last_season})"
        for row in entities_df.itertuples()
    ]
    label_to_id = dict(zip(labels, entities_df["entity_id"].tolist()))

    default_label = None
    if default_name:
        match = process.extractOne(
            default_name, labels, scorer=fuzz.WRatio, score_cutoff=60
        )
        if match:
            default_label = match[0]

    if len(query) >= 2 and len(labels) > 1:
        matches = process.extract(
            query, labels, scorer=fuzz.WRatio, limit=25, score_cutoff=40
        )
        options = [m[0] for m in matches] if matches else labels[:25]
    else:
        options = labels[:25]

    idx = 0
    if default_label and default_label in options:
        idx = options.index(default_label)

    chosen = st.selectbox(label, options, index=idx, key=key)
    return label_to_id.get(chosen)


def fuzzy_player_select(
    label: str,
    conn,
    key: str,
    default_name: str | None = None,
) -> str | None:
    """Backward-compatible alias for fuzzy_entity_select."""
    return fuzzy_entity_select(label, conn, key, default_name=default_name)


@st.cache_resource
def cached_connection():
    if not db_exists():
        return None
    conn = get_connection()
    try:
        recompute_games_played(conn)
        if players_table_needs_rebuild(conn):
            rebuild_players_table(conn)
        refresh_player_display_names(conn)
    finally:
        conn.close()
    return get_connection(read_only=True)


def get_db():
    return cached_connection()
