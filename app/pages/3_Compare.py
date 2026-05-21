"""Compare Players page."""

import numpy as np
import pandas as pd
import streamlit as st

from app.components import fuzzy_player_select, get_db, render_sidebar
from src.analytics.peer_z import peer_z_score
from src.analytics.variance import add_volume_flags, load_thresholds
from src.db.connection import db_exists
from src.db.queries import compare_players, season_stats_for_peer_analysis
from src.positions import normalize_fantasy_position
from src.scoring.calc import fp_column_for_preset, resolve_preset
from src.stats_columns import STAT_COLUMNS, build_stat_compare_frame

st.set_page_config(page_title="Compare | Fantasy Tracker", layout="wide")

controls = render_sidebar()
st.title("Compare Players")

if not db_exists():
    st.info("Ingest at least one completed season to use this page.")
    st.stop()

conn = get_db()
min_games = controls["min_games"]

col1, col2 = st.columns(2)
with col1:
    player_a = fuzzy_player_select("Player A", conn, key="compare_a")
with col2:
    player_b = fuzzy_player_select("Player B", conn, key="compare_b")

if not player_a or not player_b:
    st.stop()

mode = st.radio("Compare mode", ["All-time", "Single season"], horizontal=True)
season = controls["season"] if mode == "Single season" else None

if mode == "Single season" and season is None:
    st.warning("Select a season in the sidebar.")
    st.stop()

preset = controls["preset"]
df_a, df_b = compare_players(conn, player_a, player_b, preset, season=season)

if df_a.empty or df_b.empty:
    st.warning("Insufficient data for one or both players.")
    st.stop()

name_a = df_a["player_name"].iloc[0]
name_b = df_b["player_name"].iloc[0]


if mode == "All-time":
    total_a = df_a["fantasy_points"].sum()
    total_b = df_b["fantasy_points"].sum()
    m1, m2, m3 = st.columns(3)
    m1.metric(name_a, f"{total_a:.1f} FP (career)")
    m2.metric(name_b, f"{total_b:.1f} FP (career)")
    m3.metric("Difference", f"{total_a - total_b:+.1f}")

    merged = df_a.merge(df_b, on="season", suffixes=("_a", "_b"), how="outer").sort_values("season")
    if not merged.empty:
        merged["diff"] = merged["fantasy_points_a"].fillna(0) - merged["fantasy_points_b"].fillna(0)
        st.dataframe(
            merged[
                ["season", "fantasy_points_a", "fantasy_points_b", "diff", "teams_a", "teams_b"]
            ].round(2),
            use_container_width=True,
            hide_index=True,
        )

    pos_a = normalize_fantasy_position(df_a["position"].iloc[-1])
    pos_b = normalize_fantasy_position(df_b["position"].iloc[-1])
    st.markdown("### Career stat totals")
    totals_a = df_a[STAT_COLUMNS].sum()
    totals_b = df_b[STAT_COLUMNS].sum()
    stat_df = build_stat_compare_frame(totals_a, totals_b, name_a, name_b, [pos_a, pos_b])
    if not stat_df.empty:
        st.dataframe(stat_df.round(2), use_container_width=True, hide_index=True)

else:
    row_a = df_a.iloc[0]
    row_b = df_b.iloc[0]
    m1, m2, m3 = st.columns(3)
    m1.metric(name_a, f"{row_a['fantasy_points']:.1f} FP")
    m2.metric(name_b, f"{row_b['fantasy_points']:.1f} FP")
    m3.metric("Difference", f"{row_a['fantasy_points'] - row_b['fantasy_points']:+.1f}")

    thresholds = load_thresholds()
    peer_df = season_stats_for_peer_analysis(conn, season=season, preset=preset, min_games=min_games)
    peer_df = add_volume_flags(peer_df, min_games=min_games)

    for label, row in [(name_a, row_a), (name_b, row_b)]:
        z = peer_z_score(
            float(row["fantasy_points"]),
            peer_df,
            row["position"],
            min_peers=thresholds.get("min_qualified_peers", 10),
        )
        st.caption(
            f"{label} peer Z (season): {z:.2f}" if z is not None else f"{label}: peer Z N/A"
        )

    st.markdown("### Season stats")
    stat_df = build_stat_compare_frame(
        row_a, row_b, name_a, name_b, [row_a["position"], row_b["position"]]
    )
    if not stat_df.empty:
        st.dataframe(stat_df.round(2), use_container_width=True, hide_index=True)
