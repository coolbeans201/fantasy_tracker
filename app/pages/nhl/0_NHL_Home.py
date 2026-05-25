import streamlit as st
from app.components import get_db
from app.sport_context import init_sport_page
from app.sport_hub import render_sport_hub
from src.sports.registry import get_sport

st.set_page_config(page_title="NHL — Fantasy Tracker", page_icon="🏒", layout="wide")
init_sport_page("nhl")
render_sport_hub(get_db(), get_sport("nhl"))
