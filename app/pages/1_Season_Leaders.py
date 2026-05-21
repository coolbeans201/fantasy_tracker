"""Season Leaders page."""

import numpy as np
import streamlit as st

from app.components import get_db, render_sidebar
from src.analytics.variance import add_volume_flags, load_thresholds
from src.db.connection import db_exists
from src.db.queries import season_leaders, season_stats_for_peer_analysis, teams_for_season
from src.scoring.calc import resolve_preset
from src.stats_columns import display_stats_for_positions, rename_stats_for_display

st.set_page_config(page_title="Season Leaders | Fantasy Tracker", layout="wide")

controls = render_sidebar()
st.title("Season Leaders")

if not db_exists() or controls["season"] is None:
    st.info("Ingest at least one completed season to use this page.")
    st.stop()

conn = get_db()
season = controls["season"]
preset = controls["preset"]
min_games = controls["min_games"]

positions = st.multiselect(
    "Position",
    controls["fantasy_positions"],
    default=controls["fantasy_positions"],
    help="HB/FB count as RB. Leave empty for all skill positions.",
)
teams = ["All"] + teams_for_season(conn, season)
team_filter = st.selectbox("Team", teams)
use_splits = team_filter != "All"

df = season_leaders(
    conn,
    season,
    preset,
    positions=positions or None,
    team=team_filter if team_filter != "All" else None,
    min_games=min_games,
    use_team_splits=use_splits,
)

if df.empty:
    st.warning(
        "No results for these filters. Try lowering **Min games played** in the sidebar, "
        "clearing the position filter, or re-running ingest if you recently upgraded."
    )
    st.stop()

df["fantasy_points"] = df["fantasy_points"]
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

if controls["era_z"]:
    all_seasons = season_stats_for_peer_analysis(conn, season=None, preset=preset, min_games=min_games)
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

team_col = "team" if "team" in df.columns else "teams"
stat_cols = [c for c in display_stats_for_positions(positions) if c in df.columns]
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
display_cols = [c for c in display_cols if c in df.columns]

st.caption(
    "All stat categories are stored; columns below emphasize stats relevant to selected positions. "
    "Cross-position stats (e.g. QB rushing) are included when present."
)
shown = rename_stats_for_display(df[display_cols].round(2))
st.dataframe(shown, use_container_width=True, hide_index=True)

with st.expander("All stats"):
    extra = ["player_name", "position", team_col, "games", "fantasy_points"] + [
        c for c in display_stats_for_positions(positions) if c in df.columns
    ]
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
