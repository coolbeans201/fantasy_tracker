import streamlit as st
from app.components import get_db, render_sidebar
from app.sport_context import init_sport_page
from src.db.connection import db_exists
from src.ui_text import page_title_suffix

st.set_page_config(page_title=page_title_suffix("NBA Compare"), layout="wide")
init_sport_page("nba")
controls = render_sidebar(sport="nba")
st.title("Compare Players")
if not db_exists() or not controls["seasons"]:
    st.stop()
conn = get_db()
season = controls["season"]
rows = conn.execute(
    """
    SELECT player_name, position, team, games, fantasy_points_espn AS fantasy_points
    FROM nba_player_season_stats WHERE season = ?
    ORDER BY fantasy_points_espn DESC LIMIT 500
    """,
    [season],
).df()
a, b = st.selectbox("Player A", rows["player_name"]), st.selectbox("Player B", rows["player_name"])
ra, rb = rows[rows["player_name"] == a].iloc[0], rows[rows["player_name"] == b].iloc[0]
st.metric("Difference", f"{ra['fantasy_points'] - rb['fantasy_points']:+.1f} FP")
