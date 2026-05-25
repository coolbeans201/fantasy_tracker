"""NFL Season Leaders page."""

import streamlit as st

from app.components import get_db, render_sidebar
from app.leader_navigation import render_leaders_table
from app.sport_context import init_sport_page
from src.analytics.metrics import add_fp_per_game
from app.surprise_ui import render_surprise_highlights
from src.analytics.peer_z import enrich_leaders_dataframe
from src.analytics.surprise import (
    compute_season_surprise_frame,
    enrich_leaders_with_surprise,
)
from src.db.connection import db_exists
from src.db.queries import (
    season_has_rankings,
    season_leaders,
    season_leaders_window,
    teams_for_season,
)
from src.season_selection import format_season_label, format_season_span, metric_window_caption
from src.entities import make_dst_entity_id
from src.positions import (
    OFFENSE_POSITIONS,
    coerce_leader_selection,
    is_dst_only_selection,
    is_kicker_only_selection,
)
from src.stats_columns import (
    column_display_label,
    display_stats_for_positions,
    rename_stats_for_display,
)
from src.ui_text import page_title_suffix, title_case_ui

st.set_page_config(page_title=page_title_suffix("NFL Season Leaders"), layout="wide")
init_sport_page("nfl")

controls = render_sidebar(sport="nfl")
st.title("Season Leaders")

if not db_exists() or not controls["seasons"]:
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
seasons = controls["seasons"]
season = controls["season"]
is_window = controls["is_multi_season"]
window_label = format_season_span(seasons)
preset_key = controls["preset_key"]
min_games = controls["min_games"]
positions = _coerce_and_store()

if is_window:
    st.caption(
        f"**Window leaders** for {window_label}: totals and FP/G sum each qualified season "
        f"(min **{min_games}** games per season for offense/K)."
    )
    cap = metric_window_caption(seasons)
    if cap:
        st.caption(cap)

st.multiselect(
    title_case_ui("Position"),
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
if is_window:
    team_filter = None
    use_splits = False
elif dst_view:
    team_filter = None
    use_splits = False
else:
    teams = ["All"] + teams_for_season(conn, season)
    team_filter = st.selectbox(title_case_ui("Team"), teams)
    use_splits = team_filter != "All"

if is_window:
    df = season_leaders_window(
        conn, seasons, preset_key, positions=positions, min_games=min_games
    )
else:
    df = season_leaders(
        conn,
        season,
        preset_key,
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

surprise_all = None
if not is_window:
    df = enrich_leaders_dataframe(
        conn, df, season, preset_key, positions, min_games, era_z=controls["era_z"]
    )
    if season_has_rankings(conn, season):
        surprise_all = compute_season_surprise_frame(
            conn,
            season,
            preset_key,
            min_games=min_games,
            include_dst=dst_view,
        )
        if not surprise_all.empty:
            df = enrich_leaders_with_surprise(
                conn,
                df,
                season,
                preset_key,
                min_games=min_games,
                include_dst=dst_view,
                surprise_df=surprise_all,
            )
elif controls["era_z"]:
    st.caption("Peer Z (era) is not shown for multi-season window leaders.")
df = add_fp_per_game(df)

if dst_view:
    df["entity_id"] = df["team"].astype(str).map(make_dst_entity_id)
elif "player_id" in df.columns:
    df["entity_id"] = df["player_id"]

_SORT_OPTIONS: list[tuple[str, str]] = [
    (column_display_label("fp_per_game"), "fp_per_game"),
    (column_display_label("fantasy_points"), "fantasy_points"),
]
if not is_window:
    _SORT_OPTIONS.append((column_display_label("peer_z_season"), "peer_z_season"))
    if surprise_all is not None and not surprise_all.empty and "rank_delta" in df.columns:
        _SORT_OPTIONS.append((column_display_label("rank_delta"), "rank_delta"))
_sort_labels = [label for label, _ in _SORT_OPTIONS]
_sort_map = dict(_SORT_OPTIONS)
default_sort = 0
sort_by = st.selectbox(title_case_ui("Sort by"), _sort_labels, index=default_sort)
sort_col = _sort_map[sort_by]
if sort_col in df.columns:
    df = df.sort_values(sort_col, ascending=False, na_position="last")

stat_cols = [c for c in display_stats_for_positions(positions) if c in df.columns]
if dst_view:
    display_cols = [
        "player_name",
        "seasons_in_window",
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
        "seasons_in_window",
        "games",
        "fantasy_points",
        "fp_per_game",
        "peer_z_season",
    ]
    if "peer_z_era" in df.columns:
        display_cols.append("peer_z_era")
    for col in ("draft_ecr", "finish_rank", "rank_delta"):
        if col in df.columns:
            display_cols.append(col)
    display_cols += stat_cols
    column_labels = {}

display_cols = [c for c in display_cols if c in df.columns]
if "seasons_in_window" in display_cols and not is_window:
    display_cols.remove("seasons_in_window")


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
if surprise_all is not None and not surprise_all.empty:
    if positions:
        expanded = [p for p in positions if p in surprise_all["position"].unique()]
        if expanded:
            surprise_all = surprise_all[surprise_all["position"].isin(expanded)]
    with st.expander(title_case_ui("Winners & losers vs draft rank"), expanded=False):
        render_surprise_highlights(surprise_all, season=season)
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
    if is_window:
        st.caption("Profile links use the newest year in the sidebar window.")
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

csv_tag = format_season_label(seasons) if is_window else str(season)
st.download_button(
    "Download CSV",
    df[display_cols].to_csv(index=False),
    file_name=f"leaders_{csv_tag}.csv",
    mime="text/csv",
)
