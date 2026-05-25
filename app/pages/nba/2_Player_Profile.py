import streamlit as st
from app.components import get_db, render_sidebar
from app.sport_context import init_sport_page
from src.db.connection import db_exists
from src.sports.nba.queries import search_players
from src.ui_text import page_title_suffix

st.set_page_config(page_title=page_title_suffix("NBA Player Profile"), layout="wide")
init_sport_page("nba")
controls = render_sidebar(sport="nba")
st.title("Player Profile")
if not db_exists() or not controls["seasons"]:
    st.info("Ingest NBA data first.")
    st.stop()
conn = get_db()
q = st.text_input("Search player", "")
players = search_players(conn, q, limit=50) if q else search_players(conn, "", limit=30)
if players.empty:
    st.warning("No players found.")
    st.stop()
pick = st.selectbox("Player", players["player_name"].tolist())
row = players[players["player_name"] == pick].iloc[0]
df = conn.execute(
    "SELECT * FROM nba_player_season_stats WHERE player_id = ? AND season = ?",
    [row["player_id"], controls["season"]],
).df()
st.dataframe(df, use_container_width=True, hide_index=True)
