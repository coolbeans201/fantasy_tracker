"""Shared Streamlit UI components."""



from __future__ import annotations



import streamlit as st

from rapidfuzz import fuzz, process



from src.db.connection import (

    db_exists,

    get_connection,

    players_table_needs_rebuild,

    recompute_games_played,

    rebuild_players_table,

    refresh_player_display_names,

)

from src.db.maintenance import (
    backfill_dst_points_allowed,
    backfill_mlb_player_names,
    backfill_nba_positions,
    backfill_weekly_opponents,
)

from src.db.queries import search_fantasy_entities

from src.positions import FANTASY_POSITIONS, leader_position_options


from src.db.connection import list_sport_seasons
from src.sports.registry import get_sport, leader_position_options as sport_leader_positions
from src.season_selection import (
    SEASON_MODE_PICK,
    SEASON_MODE_RANGE,
    SEASON_MODE_SINGLE,
    is_multi_season_window,
    metric_window_caption,
    resolve_season_window,
    sidebar_window_caption,
)
from src.settings import get_min_games_default
from app.scoring_ui import render_scoring_sidebar
from src.ui_text import title_case_ui

_SIDEBAR_MODE_LABELS = {
    SEASON_MODE_SINGLE: "Single Season",
    SEASON_MODE_RANGE: "Season Range",
    SEASON_MODE_PICK: "Pick Seasons",
}
_SIDEBAR_LABEL_TO_MODE = {v: k for k, v in _SIDEBAR_MODE_LABELS.items()}





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





def _empty_sidebar_controls() -> dict:
    return {
        "season": None,
        "seasons": [],
        "season_mode": SEASON_MODE_SINGLE,
        "is_multi_season": False,
        "preset": "Half-PPR",
        "preset_key": "half_ppr",
        "era_z": False,
        "min_games": get_min_games_default(),
        "fantasy_positions": leader_position_options(),
    }


def render_sidebar(
    *,
    sport: str = "nfl",
    default_season: int | None = None,
    season_options: list[int] | None = None,
    season_scope_caption: str | None = None,
) -> dict:
    """Global sidebar controls for a single sport (no cross-sport switching)."""
    meta = get_sport(sport)
    st.sidebar.title(f"{meta.icon} {meta.label}")
    st.sidebar.caption(f"{meta.label} completed-season analytics")

    if not db_exists():
        st.sidebar.warning("No database found. Run ingest first.")
        return _empty_sidebar_controls()

    conn = get_db()
    if conn is None:
        st.sidebar.warning("No database found. Run ingest first.")
        return _empty_sidebar_controls()

    ingested = list_sport_seasons(conn, sport)
    if season_options is not None:
        allowed = sorted(set(season_options) & set(ingested), reverse=True)
    else:
        allowed = ingested
    if not allowed:
        st.sidebar.warning("No seasons ingested.")
        return _empty_sidebar_controls()

    if sport == "nfl":
        preset_label, preset_key = render_scoring_sidebar(conn)
    else:
        preset_label, preset_key = "ESPN", "espn"
        st.sidebar.caption("Scoring: **ESPN** default points (v1).")

    if "sidebar_season_mode" not in st.session_state:
        st.session_state.sidebar_season_mode = SEASON_MODE_SINGLE

    _mode_keys = list(_SIDEBAR_MODE_LABELS.keys())
    _prev_mode = st.session_state.get("sidebar_season_mode", SEASON_MODE_SINGLE)
    _radio_index = _mode_keys.index(_prev_mode) if _prev_mode in _mode_keys else 0

    mode_label = st.sidebar.radio(
        title_case_ui("Season view"),
        list(_SIDEBAR_MODE_LABELS.values()),
        index=_radio_index,
        horizontal=True,
        key="sidebar_season_mode_radio",
    )
    mode = _SIDEBAR_LABEL_TO_MODE[mode_label]
    st.session_state.sidebar_season_mode = mode

    ingested_asc = sorted(allowed)
    season_default = default_season if default_season in allowed else allowed[0]

    if mode == SEASON_MODE_SINGLE:
        season_index = allowed.index(season_default)
        single_year = st.sidebar.selectbox(
            title_case_ui("Season"), allowed, index=season_index
        )
        window_seasons = resolve_season_window(
            allowed, SEASON_MODE_SINGLE, single_year=int(single_year)
        )
    elif mode == SEASON_MODE_RANGE:
        default_lo = min(season_default, allowed[-1])
        default_hi = max(season_default, allowed[0])
        c_from, c_to = st.sidebar.columns(2)
        range_start = c_from.selectbox(
            title_case_ui("From"),
            ingested_asc,
            index=ingested_asc.index(min(default_lo, default_hi)),
            key="sidebar_range_start",
        )
        range_end = c_to.selectbox(
            title_case_ui("To"),
            ingested_asc,
            index=ingested_asc.index(max(default_lo, default_hi)),
            key="sidebar_range_end",
        )
        window_seasons = resolve_season_window(
            allowed,
            SEASON_MODE_RANGE,
            range_start=int(range_start),
            range_end=int(range_end),
        )
    else:
        pick_default = allowed[: min(5, len(allowed))]
        picked = st.sidebar.multiselect(
            title_case_ui("Seasons"),
            options=allowed,
            default=pick_default,
            key="sidebar_season_pick",
        )
        window_seasons = resolve_season_window(
            allowed, SEASON_MODE_PICK, picked=picked
        )

    st.sidebar.caption(sidebar_window_caption(window_seasons, mode=mode))
    if season_scope_caption:
        st.sidebar.caption(season_scope_caption)
    metric_cap = metric_window_caption(window_seasons)
    if metric_cap:
        st.sidebar.caption(metric_cap)

    if not window_seasons:
        st.sidebar.warning("Select at least one season in this window.")

    default_min = get_min_games_default()
    max_games = {"nfl": 17, "mlb": 162, "nba": 82, "nhl": 82}.get(sport, 82)
    min_games = st.sidebar.slider(
        title_case_ui("Min games played"),
        min_value=1,
        max_value=max_games,
        value=min(default_min, max_games),
        help=f"Default {default_min} (config/settings.yaml)",
    )
    era_z = False
    if sport == "nfl":
        era_z = st.sidebar.checkbox(title_case_ui("Show peer Z (all-time era)"), value=False)
        if st.sidebar.button(
            title_case_ui("Repair database"),
            help="Rebuild player index and refresh games played.",
        ):
            run_database_maintenance()
            st.sidebar.success("Database maintenance finished.")
            st.rerun()

    detail_season = window_seasons[0] if window_seasons else None
    return {
        "season": detail_season,
        "seasons": window_seasons,
        "season_mode": mode,
        "is_multi_season": is_multi_season_window(window_seasons),
        "preset": preset_label,
        "preset_key": preset_key,
        "era_z": era_z,
        "min_games": min_games,
        "fantasy_positions": sport_leader_positions(sport),
        "sport": sport,
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
        backfill_dst_points_allowed(conn)
        backfill_mlb_player_names(conn)
        backfill_nba_positions(conn)

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

    return get_connection()





def get_db():

    return cached_connection()


