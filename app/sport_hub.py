"""Shared sport hub landing page content."""

from __future__ import annotations

import duckdb
import streamlit as st

from app.sport_data_coverage_ui import render_sport_data_coverage
from src.db.connection import db_exists, get_ingest_summary, list_sport_seasons
from src.sports.registry import SportMeta, get_sport
from src.ui_text import title_case_ui


def render_sport_hub(conn, meta: SportMeta) -> None:
    st.title(f"{meta.icon} Fantasy Tracker — {meta.label}")
    st.markdown(
        f"**{meta.label}** completed-season analytics. "
        f"Data: {meta.data_source}. ({meta.license_note})"
    )
    st.caption(meta.season_label_hint)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.page_link(
            meta.leaders_page,
            label=title_case_ui("Season Leaders"),
            icon="📊",
        )
    with c2:
        st.page_link(
            meta.profile_page,
            label=title_case_ui("Player Profile"),
            icon="👤",
        )
    with c3:
        st.page_link(meta.compare_page, label=title_case_ui("Compare"), icon="⚖️")

    st.divider()
    if meta.sport_id != "nfl" and conn is not None:
        render_sport_data_coverage(conn, meta)
        st.divider()

    st.subheader(title_case_ui("Database status"))
    if not db_exists():
        st.warning("No database found. Run ingest first.")
    elif conn is None:
        st.warning("Could not open database.")
    else:
        seasons = list_sport_seasons(conn, meta.sport_id)
        if meta.sport_id == "nfl":
            summary = get_ingest_summary(conn)
            if summary["seasons"]:
                st.success(
                    f"**{summary['season_count']}** NFL seasons loaded. "
                    f"Latest: **{summary['latest_season']}**."
                )
        elif seasons:
            st.success(f"**{len(seasons)}** seasons loaded. Latest: **{seasons[0]}**.")
            try:
                row = conn.execute(
                    f"SELECT COUNT(*) FROM {meta.manifest_table}"
                ).fetchone()
                if row and row[0]:
                    st.caption(f"Ingest manifest: **{row[0]}** season entries.")
            except duckdb.Error:
                pass
            st.caption(f"Seasons: {', '.join(str(s) for s in seasons)}")
        else:
            st.info(f"No {meta.label} seasons ingested yet.")

    st.divider()
    st.subheader(title_case_ui("Ingest"))
    st.code(meta.ingest_command, language="powershell")
