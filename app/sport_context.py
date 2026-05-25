"""Active sport scope for Streamlit pages (no cross-sport mixing)."""

from __future__ import annotations

import streamlit as st

from src.sports.registry import DEFAULT_SPORT, get_sport

SESSION_KEY = "active_sport"


def set_active_sport(sport_id: str) -> None:
    st.session_state[SESSION_KEY] = get_sport(sport_id).sport_id


def get_active_sport() -> str:
    return str(st.session_state.get(SESSION_KEY, DEFAULT_SPORT))


def init_sport_page(sport_id: str) -> None:
    """Call at top of each sport-scoped page."""
    set_active_sport(sport_id)
