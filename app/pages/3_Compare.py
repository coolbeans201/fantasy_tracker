"""Compare Players page."""

import numpy as np
import pandas as pd
import streamlit as st

from app.components import fuzzy_player_select, get_db, render_sidebar
from src.analytics.peer_z import peer_z_score
from src.analytics.variance import add_volume_flags, load_thresholds
from src.db.connection import db_exists
from src.db.queries import (
    compare_entities,
    dst_season_stats_for_peer_analysis,
    entity_display_label,
    entity_seasons_available,
    season_stats_for_peer_analysis,
)
from src.positions import (
    COMPARE_GROUP_DST,
    COMPARE_GROUP_KICKER,
    COMPARE_GROUP_OFFENSE,
    DST_POSITION,
    compare_cohort,
    compare_cohorts_compatible,
    compare_incompatible_message,
    is_dst_position,
    normalize_fantasy_position,
)
from src.stats_columns import (
    build_stat_compare_frame,
    display_stats_for_positions,
    rename_compare_career_merge,
    rename_stats_for_display,
)
from src.ui_text import section_h3


def _profile_position_key(position: str | None) -> str:
    if is_dst_position(position):
        return DST_POSITION
    return normalize_fantasy_position(position) or str(position)


def _peer_df_for_season(conn, season: int, preset: str, min_games: int, position: str | None):
    if is_dst_position(position):
        return dst_season_stats_for_peer_analysis(conn, season=season, min_games=min_games)
    return season_stats_for_peer_analysis(
        conn, season=season, preset=preset, min_games=min_games
    )

st.set_page_config(page_title="Compare | Fantasy Tracker", layout="wide")

controls = render_sidebar()
st.title("Compare Players")
st.caption(
    "QB, RB, WR, and TE can be compared to each other. "
    "Compare kickers to kickers and team defenses (DST) to other defenses only."
)

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

if "compare_mode" not in st.session_state:
    st.session_state.compare_mode = "All-time"

st.radio(
    "Compare mode",
    ["All-time", "Single season"],
    horizontal=True,
    key="compare_mode",
)
mode = str(st.session_state.compare_mode)
compare_season = (
    int(controls["season"]) if mode == "Single season" else None
)

if mode == "Single season" and compare_season is None:
    st.warning("Select a season in the sidebar.")
    st.stop()

if mode == "Single season":
    st.caption(
        f"Comparing the **{compare_season}** season (sidebar **Season** control)."
    )
else:
    st.caption(
        "All-time mode uses every ingested season. The sidebar **Season** year is ignored."
    )

preset = controls["preset"]
df_a, df_b = compare_entities(
    conn, player_a, player_b, preset, season=compare_season
)

if df_a.empty or df_b.empty:
    label_a = entity_display_label(conn, player_a)
    label_b = entity_display_label(conn, player_b)
    if mode == "Single season":
        if df_a.empty:
            st.warning(
                f"**{label_a}** has no stats for **{compare_season}** in the database."
            )
            avail = entity_seasons_available(conn, player_a, preset)
            if avail:
                st.caption(
                    f"{label_a} seasons available: {avail[0]}–{avail[-1]} "
                    f"({len(avail)} years ingested)."
                )
        if df_b.empty:
            st.warning(
                f"**{label_b}** has no stats for **{compare_season}** in the database."
            )
            avail = entity_seasons_available(conn, player_b, preset)
            if avail:
                st.caption(
                    f"{label_b} seasons available: {avail[0]}–{avail[-1]} "
                    f"({len(avail)} years ingested)."
                )
        st.info(
            "Single-season compare needs a regular-season row for **both** sides that year. "
            "Injured or inactive players often have no row (e.g. Andrew Luck did not play in 2017)."
        )
    else:
        st.warning("Insufficient data for one or both selections.")
    st.stop()

name_a = entity_display_label(conn, player_a)
name_b = entity_display_label(conn, player_b)

cohort_a = compare_cohort(player_a, df_a["position"].iloc[-1])
cohort_b = compare_cohort(player_b, df_b["position"].iloc[-1])
if not compare_cohorts_compatible(cohort_a, cohort_b):
    st.error(compare_incompatible_message(cohort_a, cohort_b))
    st.stop()


def _compare_stat_positions(pos_a: str, pos_b: str) -> list[str]:
    if cohort_a == COMPARE_GROUP_DST:
        return [DST_POSITION]
    if cohort_a == COMPARE_GROUP_KICKER:
        return ["K"]
    return [_profile_position_key(pos_a), _profile_position_key(pos_b)]


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
        merge_cols = ["season", "fantasy_points_a", "fantasy_points_b", "diff"]
        if cohort_a != COMPARE_GROUP_DST:
            merge_cols.extend(["teams_a", "teams_b"])
        st.dataframe(
            rename_compare_career_merge(
                merged[merge_cols].round(2),
                name_a,
                name_b,
                include_teams=cohort_a != COMPARE_GROUP_DST,
            ),
            use_container_width=True,
            hide_index=True,
        )

    pos_a = df_a["position"].iloc[-1]
    pos_b = df_b["position"].iloc[-1]
    st.markdown(section_h3("Career stat totals"))
    stat_positions = _compare_stat_positions(pos_a, pos_b)
    stat_cols = list(dict.fromkeys(display_stats_for_positions(stat_positions)))
    totals_a = df_a[[c for c in stat_cols if c in df_a.columns]].sum(numeric_only=True)
    totals_b = df_b[[c for c in stat_cols if c in df_b.columns]].sum(numeric_only=True)
    stat_df = build_stat_compare_frame(totals_a, totals_b, name_a, name_b, stat_positions)
    if not stat_df.empty:
        st.dataframe(
            rename_stats_for_display(stat_df.round(2)),
            use_container_width=True,
            hide_index=True,
        )

else:
    row_a = df_a.iloc[0]
    row_b = df_b.iloc[0]
    m1, m2, m3 = st.columns(3)
    m1.metric(name_a, f"{row_a['fantasy_points']:.1f} FP")
    m2.metric(name_b, f"{row_b['fantasy_points']:.1f} FP")
    m3.metric("Difference", f"{row_a['fantasy_points'] - row_b['fantasy_points']:+.1f}")

    thresholds = load_thresholds()
    for label, row in [(name_a, row_a), (name_b, row_b)]:
        peer_df = _peer_df_for_season(
            conn, compare_season, preset, min_games, row["position"]
        )
        peer_df = add_volume_flags(peer_df, min_games=min_games)
        z = peer_z_score(
            float(row["fantasy_points"]),
            peer_df,
            row["position"],
            min_peers=thresholds.get("min_qualified_peers", 10),
        )
        st.caption(
            f"{label} peer Z (season): {z:.2f}" if z is not None else f"{label}: peer Z N/A"
        )

    st.markdown(section_h3("Season stats"))
    stat_df = build_stat_compare_frame(
        row_a,
        row_b,
        name_a,
        name_b,
        _compare_stat_positions(row_a["position"], row_b["position"]),
    )
    if not stat_df.empty:
        st.dataframe(
            rename_stats_for_display(stat_df.round(2)),
            use_container_width=True,
            hide_index=True,
        )
