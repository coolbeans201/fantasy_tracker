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

from src.db.maintenance import backfill_weekly_opponents

from src.db.queries import search_fantasy_entities

from src.positions import FANTASY_POSITIONS, leader_position_options

from src.scoring.calc import DISPLAY_PRESETS

from src.settings import get_min_games_default





def _parse_query_int(value: str | None) -> int | None:

    if value is None:

        return None

    try:

        return int(str(value).strip())

    except (TypeError, ValueError):

        return None





def query_param_season() -> int | None:

    """Season year from URL query params (?season=2023)."""

    raw = st.query_params.get("season")

    if isinstance(raw, list):

        raw = raw[0] if raw else None

    return _parse_query_int(raw)





def query_param_entity() -> str | None:

    """Entity id from URL (?entity=player_id or dst:TEAM)."""

    raw = st.query_params.get("entity")

    if isinstance(raw, list):

        raw = raw[0] if raw else None

    text = str(raw or "").strip()

    return text or None





def render_sidebar(
    *,
    default_season: int | None = None,
    season_options: list[int] | None = None,
    season_scope_caption: str | None = None,
) -> dict:
    """Global sidebar controls."""
    st.sidebar.title("Fantasy Tracker")
    st.sidebar.caption("NFL completed-season analytics")

    if not db_exists():
        st.sidebar.warning("No database found. Run ingest first.")
        return {"season": None, "preset": "Half-PPR", "era_z": False, "min_games": get_min_games_default()}

    if season_options is not None:
        seasons = sorted(season_options, reverse=True)
    else:
        seasons = list_ingested_seasons()
    if not seasons:
        st.sidebar.warning("No seasons ingested.")
        return {"season": None, "preset": "Half-PPR", "era_z": False, "min_games": get_min_games_default()}

    preset = st.sidebar.selectbox("Scoring", list(DISPLAY_PRESETS.keys()), index=1)

    season_default = default_season if default_season in seasons else seasons[0]
    season_index = seasons.index(season_default)
    season = st.sidebar.selectbox("Season", seasons, index=season_index)
    if season_scope_caption:
        st.sidebar.caption(season_scope_caption)

    default_min = get_min_games_default()

    min_games = st.sidebar.slider(

        "Min games played",

        min_value=1,

        max_value=17,

        value=default_min,

        help=f"Default {default_min} (config/settings.yaml) — half-season threshold",

    )

    era_z = st.sidebar.checkbox("Show peer Z (all-time era)", value=False)



    if st.sidebar.button("Repair database", help="Rebuild player index and refresh games played."):

        run_database_maintenance()

        st.sidebar.success("Database maintenance finished.")

        st.rerun()



    return {

        "season": season,

        "preset": preset,

        "era_z": era_z,

        "min_games": min_games,

        "fantasy_positions": leader_position_options(),

    }





def run_database_maintenance() -> None:

    """Run games/players maintenance (ingest also does this)."""

    conn = get_connection()

    try:

        recompute_games_played(conn)

        if players_table_needs_rebuild(conn):

            rebuild_players_table(conn)

        refresh_player_display_names(conn)
        backfill_weekly_opponents(conn)

    finally:

        conn.close()

    cached_connection.clear()





def fuzzy_entity_select(

    label: str,

    conn,

    key: str,

    default_name: str | None = None,

    *,

    preset_entity_id: str | None = None,

) -> str | None:

    """Fuzzy autocomplete picker. Returns player_id or dst:TEAM for team defenses."""

    if preset_entity_id:

        st.caption(f"Loaded from link: `{preset_entity_id}`")

        if st.button("Clear linked player", key=f"{key}_clear_link"):

            st.query_params.clear()

            st.rerun()

        return preset_entity_id



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

    return get_connection(read_only=True)





def get_db():

    return cached_connection()


