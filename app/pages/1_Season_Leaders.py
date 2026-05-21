"""Season Leaders page."""

import numpy as np
import streamlit as st

from app.components import get_db, render_sidebar
from src.analytics.variance import add_volume_flags, load_thresholds
from src.db.connection import db_exists
from src.db.queries import season_leaders, season_stats_for_peer_analysis, teams_for_season
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
    """Update widget state before render / in on_change only (not after widget)."""
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

df["fantasy_points"] = df["fantasy_points"]

if not dst_view:
    df = add_volume_flags(df, min_games=min_games)

    thresholds = load_thresholds()
    min_peers = thresholds.get("min_qualified_peers", 10)
    df["peer_z_season"] = np.nan

    qualified = df[df["peer_qualified"]]
    for pos, group in qualified.groupby("position"):
        if len(group) < min_peers:
            continue
        mean, std = group["fantasy_points"].mean(), group["fantasy_points"].std()
        if std and std > 0:
            df.loc[group.index, "peer_z_season"] = (group["fantasy_points"] - mean) / std

if controls["era_z"] and not dst_view:
    all_seasons = season_stats_for_peer_analysis(conn, season=None, preset=preset, min_games=min_games)
    if is_kicker_only_selection(positions):
        all_seasons = all_seasons[all_seasons["position"] == "K"]
    elif not is_dst_only_selection(positions):
        all_seasons = all_seasons[all_seasons["position"].isin(OFFENSE_POSITIONS)]
    all_seasons = add_volume_flags(all_seasons, min_games=min_games)
    era_stats = (
        all_seasons[all_seasons["peer_qualified"]]
        .groupby("position")["fantasy_points"]
        .agg(era_mean="mean", era_std="std")
        .reset_index()
    )
    df = df.merge(era_stats, on="position", how="left")
    df["peer_z_era"] = np.where(
        (df["era_std"] > 0) & df["peer_qualified"],
        (df["fantasy_points"] - df["era_mean"]) / df["era_std"],
        np.nan,
    )
    df = df.drop(columns=["era_mean", "era_std"], errors="ignore")

stat_cols = [c for c in display_stats_for_positions(positions) if c in df.columns]
if dst_view:
    display_cols = ["player_name", "games", "fantasy_points", *stat_cols]
    column_labels = {"player_name": "Team"}
else:
    team_col = "team" if "team" in df.columns else "teams"
    display_cols = [
        "player_name",
        "position",
        team_col,
        "games",
        "fantasy_points",
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
    stat_hint = "One row per NFL team. ESPN D/ST scoring and defense stats only."
elif is_kicker_only_selection(positions):
    stat_hint = "Showing kicker stats only."
else:
    stat_hint = (
        "Stat columns match selected offensive positions; kicker and DST stats are hidden."
    )
st.caption(stat_hint)
shown = _rename_leader_table(df[display_cols].round(2), column_labels)
st.dataframe(shown, use_container_width=True, hide_index=True)

if not dst_view:
    with st.expander(title_case_ui("All stats")):
        team_col = "team" if "team" in df.columns else "teams"
        extra = ["player_name", "position", team_col, "games", "fantasy_points"] + stat_cols
        st.dataframe(
            rename_stats_for_display(df[extra].round(2)),
            use_container_width=True,
            hide_index=True,
        )

st.download_button(
    "Download CSV",
    df[display_cols].to_csv(index=False),
    file_name=f"leaders_{season}.csv",
    mime="text/csv",
)
