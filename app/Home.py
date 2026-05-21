"""Fantasy Tracker — home page."""

import streamlit as st

from app.components import render_sidebar
from src.db.connection import db_exists, list_ingested_seasons
from src.ui_text import title_case_ui

st.set_page_config(
    page_title="Fantasy Tracker",
    page_icon="🏈",
    layout="wide",
)

render_sidebar()

st.title("Fantasy Tracker")
st.markdown(
    "Explore **completed NFL regular seasons** with standard, half-PPR, and full PPR scoring. "
    "Analyze season leaders, player careers, head-to-head comparisons, and variance vs peers."
)

st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("pages/1_Season_Leaders.py", label="Season Leaders", icon="📊")
    st.caption("Best players by season, position, and team filters.")
with col2:
    st.page_link("pages/2_Player_Profile.py", label="Player Profile", icon="👤")
    st.caption("Career breakdown, best week, and Z-scores.")
with col3:
    st.page_link("pages/3_Compare.py", label="Compare Players", icon="⚖️")
    st.caption("All-time or single-season head-to-head.")

st.divider()

st.subheader(title_case_ui("Getting started"))
st.code(
    ".\\.venv\\Scripts\\python.exe scripts\\ingest_season.py --season 2023\n"
    ".\\.venv\\Scripts\\python.exe -m streamlit run app/Home.py",
    language="powershell",
)

if db_exists():
    seasons = list_ingested_seasons()
    if seasons:
        st.success(f"Loaded seasons: {', '.join(str(s) for s in sorted(seasons))}")
    else:
        st.info("Database exists but no seasons ingested yet.")
else:
    st.warning("No database at `data/fantasy_tracker.duckdb`. Run ingest to begin.")

st.caption("Data coverage: nflverse (~1999+). Regular season only. Ingest new seasons after they complete.")
