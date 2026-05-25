"""Register all Streamlit pages (nested paths under pages/ are not auto-discovered)."""

from __future__ import annotations

import streamlit as st

from src.sports.registry import list_sports


def run_app() -> None:
    sections: dict[str, list[st.Page]] = {
        "Fantasy Tracker": [
            st.Page("pages_home.py", title="Home", icon="🏆", default=True, url_path="home"),
        ],
    }
    for meta in list_sports():
        sid = meta.sport_id
        sections[meta.label] = [
            st.Page(meta.hub_page, title="Overview", icon=meta.icon, url_path=f"{sid}_overview"),
            st.Page(
                meta.leaders_page,
                title="Season Leaders",
                icon="📊",
                url_path=f"{sid}_leaders",
            ),
            st.Page(
                meta.profile_page,
                title="Player Profile",
                icon="👤",
                url_path=f"{sid}_profile",
            ),
            st.Page(
                meta.compare_page,
                title="Compare",
                icon="⚖️",
                url_path=f"{sid}_compare",
            ),
        ]
    st.navigation(sections).run()
