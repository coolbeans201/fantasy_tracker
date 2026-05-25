import streamlit as st
from app.components import get_db, render_sidebar
from app.sport_context import init_sport_page
from src.db.connection import db_exists
from src.sports.nhl.positions import GOALIE_POSITION, SKATER_POSITION
from src.ui_text import page_title_suffix

st.set_page_config(page_title=page_title_suffix("NHL Compare"), layout="wide")
init_sport_page("nhl")
controls = render_sidebar(sport="nhl")
st.title("Compare Players")
st.caption("Compare **skaters to skaters** or **goalies to goalies** only.")
if not db_exists() or not controls["seasons"]:
    st.stop()
conn = get_db()
season = controls["season"]
cohort = st.radio("Cohort", [SKATER_POSITION, GOALIE_POSITION], horizontal=True)
rows = conn.execute(
    """
    SELECT player_name, position, team, games, fantasy_points_espn AS fantasy_points
    FROM nhl_player_season_stats WHERE season = ? AND position = ?
    ORDER BY fantasy_points_espn DESC LIMIT 500
    """,
    [season, cohort],
).df()
a, b = st.selectbox("Player A", rows["player_name"]), st.selectbox("Player B", rows["player_name"])
ra, rb = rows[rows["player_name"] == a].iloc[0], rows[rows["player_name"] == b].iloc[0]
st.metric("Difference", f"{ra['fantasy_points'] - rb['fantasy_points']:+.1f} FP")
