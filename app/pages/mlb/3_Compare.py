import duckdb
import pandas as pd
import streamlit as st

from app.sport_compare_page import render_sport_compare_page
from src.sports.mlb.positions import FIELD_POSITIONS, PITCHER_POSITIONS
from src.ui_text import title_case_ui


def _load_mlb_rows(conn: duckdb.DuckDBPyConnection, season: int) -> pd.DataFrame:
    cohort = st.radio(
        title_case_ui("Cohort"),
        ["Hitters", "Pitchers"],
        horizontal=True,
        key="mlb_compare_cohort",
    )
    if cohort == "Pitchers":
        pos_filter = PITCHER_POSITIONS
    else:
        pos_filter = FIELD_POSITIONS + ["H"]
    placeholders = ", ".join("?" * len(pos_filter))
    return conn.execute(
        f"""
        SELECT player_id, player_name, position, team, games,
               fantasy_points_espn AS fantasy_points
        FROM mlb_player_season_stats
        WHERE season = ? AND position IN ({placeholders})
        ORDER BY fantasy_points_espn DESC
        LIMIT 500
        """,
        [season, *pos_filter],
    ).df()


render_sport_compare_page(
    "mlb",
    label="MLB",
    caption="Compare **hitters to hitters** or **pitchers to pitchers** only.",
    load_rows=_load_mlb_rows,
)
