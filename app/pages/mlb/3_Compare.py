import streamlit as st
from app.components import get_db, render_sidebar
from app.sport_context import init_sport_page
from src.db.connection import db_exists
from src.sports.mlb.positions import HITTER_POSITION, PITCHER_POSITION
from src.ui_text import page_title_suffix

st.set_page_config(page_title=page_title_suffix("MLB Compare"), layout="wide")
init_sport_page("mlb")
controls = render_sidebar(sport="mlb")
st.title("Compare Players")
st.caption("Compare **hitters to hitters** or **pitchers to pitchers** only.")
if not db_exists() or not controls["seasons"]:
    st.stop()
conn = get_db()
season = controls["season"]
cohort = st.radio("Cohort", [HITTER_POSITION, PITCHER_POSITION], horizontal=True)
rows = conn.execute(
    """
    SELECT player_name, position, team, games, fantasy_points_espn AS fantasy_points
    FROM mlb_player_season_stats
    WHERE season = ? AND position = ?
    ORDER BY fantasy_points_espn DESC
    LIMIT 500
    """,
    [season, cohort],
).df()
if rows.empty:
    st.warning("No data.")
    st.stop()
a = st.selectbox("Player A", rows["player_name"])
b = st.selectbox("Player B", rows["player_name"])
ra = rows[rows["player_name"] == a].iloc[0]
rb = rows[rows["player_name"] == b].iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric(a, f"{ra['fantasy_points']:.1f} FP")
c2.metric(b, f"{rb['fantasy_points']:.1f} FP")
c3.metric("Diff", f"{ra['fantasy_points'] - rb['fantasy_points']:+.1f}")
