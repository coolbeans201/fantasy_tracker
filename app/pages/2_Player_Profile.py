"""Player Profile page (players and team defenses)."""

import numpy as np
import streamlit as st

from app.charts import season_fantasy_points_chart
from app.components import fuzzy_entity_select, get_db, render_sidebar
from src.analytics.peer_z import peer_z_score
from src.analytics.variance import add_volume_flags, compute_career_z, load_thresholds
from src.db.connection import db_exists
from src.db.queries import (
    dst_season_stats_for_peer_analysis,
    entity_seasons,
    entity_weekly,
    player_team_splits,
    season_stats_for_peer_analysis,
)
from src.entities import dst_display_name, dst_team_from_entity, is_dst_entity
from src.positions import DST_POSITION, normalize_fantasy_position
from src.stats_columns import display_stats_for_positions, rename_stats_for_display
from src.ui_text import section_h3, title_case_ui

st.set_page_config(page_title="Player Profile | Fantasy Tracker", layout="wide")

controls = render_sidebar()
st.title("Player Profile")
st.caption("Search for a player (QB/RB/WR/TE/K) or a team defense (e.g. DEN).")

if not db_exists():
    st.info("Ingest at least one completed season to use this page.")
    st.stop()

conn = get_db()
entity_id = fuzzy_entity_select("player or defense", conn, key="profile_entity")

if not entity_id:
    st.stop()

dst_view = is_dst_entity(entity_id)
preset = controls["preset"]
min_games = controls["min_games"]
seasons_df = entity_seasons(conn, entity_id, preset)

if seasons_df.empty:
    st.warning("No season data for this selection.")
    st.stop()

if dst_view:
    team = dst_team_from_entity(entity_id)
    display_name = dst_display_name(team)
    primary_pos = DST_POSITION
    st.subheader(f"{display_name} ({primary_pos})")
    st.caption("Fantasy points use ESPN default D/ST scoring (not the sidebar offensive preset).")
else:
    display_name = (
        seasons_df["player_name"].iloc[0]
        if "player_name" in seasons_df.columns
        else entity_id
    )
    primary_pos = (
        normalize_fantasy_position(seasons_df["position"].iloc[-1])
        or seasons_df["position"].iloc[-1]
    )
    st.subheader(f"{display_name} ({primary_pos})")

career = compute_career_z(seasons_df, min_games=min_games)
stat_cols = display_stats_for_positions([primary_pos])
career_cols = ["season", "teams", "games", "fantasy_points", "best_week", "best_week_fp"]
if "career_z" in career.columns:
    career_cols.append("career_z")
career_cols += [c for c in stat_cols if c in career.columns]
career_show = rename_stats_for_display(career[career_cols].round(2))

if controls["season"]:
    thresholds = load_thresholds()
    season_row = seasons_df[seasons_df["season"] == controls["season"]]
    if not season_row.empty:
        if dst_view:
            peer_df = dst_season_stats_for_peer_analysis(
                conn, season=controls["season"], min_games=min_games
            )
        else:
            peer_df = season_stats_for_peer_analysis(
                conn, season=controls["season"], preset=preset, min_games=min_games
            )
        peer_df = add_volume_flags(peer_df, min_games=min_games)
        fp = float(season_row.iloc[0]["fantasy_points"])
        peer_z = peer_z_score(
            fp,
            peer_df,
            season_row.iloc[0]["position"],
            min_peers=thresholds.get("min_qualified_peers", 10),
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Season FP", f"{fp:.1f}")
        if peer_z is not None:
            c2.metric("Peer Z (season)", f"{peer_z:.2f}")
            cz_row = career[career["season"] == controls["season"]]
            if (
                not cz_row.empty
                and bool(cz_row["peer_qualified"].iloc[0])
                and not np.isnan(cz_row["career_z"].iloc[0])
            ):
                c3.metric("Career Z", f"{cz_row['career_z'].iloc[0]:.2f}")

st.markdown(section_h3("Career by season"))
if dst_view:
    st.caption(
        "One row per season for this team's defense/special teams unit. "
        "**Career Z** uses only seasons meeting min games (sidebar)."
    )
else:
    st.caption(
        "Primary columns match the player's position; rushing/passing stats appear for QBs and "
        "other cross-role production. **Career Z** uses only seasons meeting min games and "
        "position volume gates (same as peer Z). Expand below for every stored stat."
    )
st.dataframe(career_show, use_container_width=True, hide_index=True)

with st.expander(title_case_ui("All career stats")):
    all_career = ["season", "teams", "games", "fantasy_points"] + [
        c for c in display_stats_for_positions([primary_pos]) if c in career.columns
    ]
    st.dataframe(
        rename_stats_for_display(career[all_career].round(2)),
        use_container_width=True,
        hide_index=True,
    )

st.markdown(section_h3("Fantasy points by season"))
if dst_view and len(career) >= 15:
    st.caption("Long career span — axis shows every few seasons for readability.")
season_fantasy_points_chart(career, dense=dst_view)

if controls["season"]:
    if not dst_view:
        splits = player_team_splits(conn, entity_id, controls["season"], preset)
        if len(splits) > 1:
            st.markdown(section_h3(f"Team splits ({controls['season']})"))
            split_cols = ["team", "games", "fantasy_points"] + [
                c for c in stat_cols if c in splits.columns
            ]
            st.dataframe(
                rename_stats_for_display(splits[split_cols].round(2)),
                use_container_width=True,
                hide_index=True,
            )

    weekly = entity_weekly(conn, entity_id, controls["season"], preset)
    if not weekly.empty:
        st.markdown(section_h3(f"Weekly ({controls['season']})"))
        week_cols = ["week", "fantasy_points"] + [c for c in stat_cols if c in weekly.columns]
        if not dst_view:
            week_cols.insert(1, "team")
        st.dataframe(
            rename_stats_for_display(weekly[week_cols].round(2)),
            use_container_width=True,
            hide_index=True,
        )
