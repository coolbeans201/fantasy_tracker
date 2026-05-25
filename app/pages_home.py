"""Global home — pick a sport (used via st.navigation entrypoint)."""

import streamlit as st

from app.components import get_db
from src.db.connection import db_exists
from src.sports.registry import list_sports, sport_has_ingested_data
from src.ui_text import title_case_ui

st.set_page_config(
    page_title="Fantasy Tracker",
    page_icon="🏆",
    layout="wide",
)

st.title("Fantasy Tracker")
st.markdown(
    "Historical fantasy analytics by sport. Pick a league below — each sport has its own "
    "leaders, profiles, and comparisons (**no cross-sport** compare)."
)

conn = get_db() if db_exists() else None

st.subheader(title_case_ui("Choose a sport"))

cols = st.columns(len(list_sports()))
for col, meta in zip(cols, list_sports()):
    with col:
        has_data = sport_has_ingested_data(conn, meta.sport_id) if conn else False
        badge = " ✓" if has_data else ""
        st.page_link(meta.hub_page, label=f"{meta.icon} {meta.label}{badge}", use_container_width=True)
        st.caption(meta.data_source)

st.divider()
st.caption(
    "NFL uses nflverse. MLB/NBA/NHL use separate ingest scripts — see each sport hub for commands."
)
