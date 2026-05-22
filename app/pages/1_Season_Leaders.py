"""Season Leaders page."""

import streamlit as st

from app.components import get_db, render_sidebar
from app.leader_navigation import render_leaders_table
from src.analytics.metrics import add_fp_per_game
from src.analytics.peer_z import enrich_leaders_dataframe
from src.db.connection import db_exists
from src.db.queries import season_leaders, teams_for_season
from src.entities import make_dst_entity_id
from src.positions import (
    OFFENSE_POSITIONS,
    coerce_leader_selection,
    is_dst_only_selection,
    is_kicker_only_selection,
)
from src.stats_columns import display_stats_for_positions, rename_stats_for_display
from src.ui_text import title_case_ui

st.set_page_config(page_title="Season Leaders | Fantasy Tracker", layout="wide")

controls = render_sidebar()
st.title("Season Leaders")

if not db_exists() or controls["season"] is None:
    st.info("Ingest at least one completed season to use this page.")
    st.stop()


def _coerce_and_store() -> list[str]:
    prev = st.session_state.get("leaders_positions_prev", list(OFFENSE_POSITIONS))
    raw = st.session_state.get("leaders_positions", list(OFFENSE_POSITIONS))
    coerced = coerce_leader_selection(raw, prev)
    st.session_state.leaders_positions = coerced
    st.session_state.leaders_positions_prev = coerced
    return coerced


def _coerce_leader_positions() -> None:
    _coerce_and_store()


if "leaders_positions" not in st.session_state:
    st.session_state.leaders_positions = list(OFFENSE_POSITIONS)
if "leaders_positions_prev" not in st.session_state:
    st.session_state.leaders_positions_prev = list(OFFENSE_POSITIONS)

conn = get_db()
season = controls["season"]
preset = controls["preset"]
min_games = controls["min_games"]
positions = _coerce_and_store()

st.multiselect(
    "Position",
    controls["fantasy_positions"],
    key="leaders_positions",
    on_change=_coerce_leader_positions,
    help=(
        "Default shows QB/RB/WR/TE only. Select **K** or **DST** alone for kickers or "
        "team defense (ESPN scoring). They cannot be combined with other positions."
    ),
)

if is_kicker_only_selection(positions) or is_dst_only_selection(positions):
    st.caption(
        "**K** and **DST** use ESPN default scoring (not the sidebar offensive preset)."
    )
else:
    st.caption("Uses the sidebar scoring preset for offensive positions (QB/RB/WR/TE).")

dst_view = is_dst_only_selection(positions)
if dst_view:
    team_filter = None
    use_splits = False
else:
    teams = ["All"] + teams_for_season(conn, season)
    team_filter = st.selectbox("Team", teams)
    use_splits = team_filter != "All"

df = season_leaders(
    conn,
    season,
    preset,
    positions=positions,
    team=team_filter if team_filter not in (None, "All") else None,
    min_games=min_games,
    use_team_splits=use_splits,
)

if df.empty:
    st.warning(
        "No results for these filters. Try lowering **Min games played** in the sidebar, "
        "adjusting the position filter, or re-running ingest if you recently upgraded."
    )
    st.stop()

df = enrich_leaders_dataframe(
    conn, df, season, preset, positions, min_games, era_z=controls["era_z"]
)
df = add_fp_per_game(df)

if dst_view:
    df["entity_id"] = df["team"].astype(str).map(make_dst_entity_id)
elif "player_id" in df.columns:
    df["entity_id"] = df["player_id"]

sort_options = ["FP per game", "Fantasy points", "Peer Z (season)"]
default_sort = 1 if dst_view else 0
sort_by = st.selectbox("Sort by", sort_options, index=default_sort)
sort_col = {
    "FP per game": "fp_per_game",
    "Fantasy points": "fantasy_points",
    "Peer Z (season)": "peer_z_season",
}[sort_by]
if sort_col in df.columns:
    df = df.sort_values(sort_col, ascending=False, na_position="last")

stat_cols = [c for c in display_stats_for_positions(positions) if c in df.columns]
if dst_view:
    display_cols = [
        "player_name",
        "games",
        "fantasy_points",
        "fp_per_game",
        "peer_z_season",
        *stat_cols,
    ]
    column_labels = {"player_name": "Team"}
else:
    team_col = "team" if "team" in df.columns else "teams"
    display_cols = [
        "player_name",
        "position",
        team_col,
        "games",
        "fantasy_points",
        "fp_per_game",
        "peer_z_season",
    ]
    if "peer_z_era" in df.columns:
        display_cols.append("peer_z_era")
    display_cols += stat_cols
    column_labels = {}

display_cols = [c for c in display_cols if c in df.columns]


def _rename_leader_table(frame, extra_labels: dict[str, str]):
    out = rename_stats_for_display(frame)
    for col, label in extra_labels.items():
        display_key = "Player" if col == "player_name" else col
        if display_key in out.columns:
            out = out.rename(columns={display_key: label})
    return out


if dst_view:
    stat_hint = (
        "One row per NFL team. ESPN D/ST scoring. Peer Z compares all teams that season "
        "(min games filter does not apply)."
    )
elif is_kicker_only_selection(positions):
    stat_hint = "Kicker stats with ESPN scoring. Peer Z uses kicker volume gates."
else:
    stat_hint = "Offensive stats use the sidebar scoring preset. Default sort is FP per game."
st.caption(stat_hint)
table_df = df.reset_index(drop=True)
shown = _rename_leader_table(table_df[display_cols], column_labels)
if "entity_id" in table_df.columns:
    name_col = "Team" if dst_view else "Player"
    render_leaders_table(
        shown,
        entity_ids=table_df["entity_id"],
        display_names=table_df["player_name"],
        season=season,
        name_column=name_col,
    )
else:
    st.dataframe(shown, use_container_width=True, hide_index=True)

if not dst_view:
    with st.expander(title_case_ui("All stats")):
        team_col = "team" if "team" in df.columns else "teams"
        extra = [
            "player_name",
            "position",
            team_col,
            "games",
            "fantasy_points",
            "fp_per_game",
        ] + stat_cols
        st.dataframe(
            rename_stats_for_display(df[extra]),
            use_container_width=True,
            hide_index=True,
        )

st.download_button(
    "Download CSV",
    df[display_cols].to_csv(index=False),
    file_name=f"leaders_{season}.csv",
    mime="text/csv",
)
