import duckdb
import pandas as pd
import streamlit as st

from app.sport_compare_page import render_sport_compare_page
from src.sports.nhl.positions import GOALIE_POSITION, SKATER_POSITIONS
from src.ui_text import title_case_ui


def _load_nhl_rows(conn: duckdb.DuckDBPyConnection, season: int) -> pd.DataFrame:
    cohort = st.radio(
        title_case_ui("Cohort"),
        [title_case_ui("Skaters"), title_case_ui("Goalies")],
        horizontal=True,
        key="nhl_compare_cohort",
    )
    if cohort == title_case_ui("Goalies"):
        return conn.execute(
            """
            SELECT player_id, player_name, position, team, games,
                   fantasy_points_espn AS fantasy_points
            FROM nhl_player_season_stats
            WHERE season = ? AND position = ?
            ORDER BY fantasy_points_espn DESC
            LIMIT 500
            """,
            [season, GOALIE_POSITION],
        ).df()
    skater_pos = SKATER_POSITIONS + ["S"]
    placeholders = ", ".join("?" * len(skater_pos))
    return conn.execute(
        f"""
        SELECT player_id, player_name, position, team, games,
               fantasy_points_espn AS fantasy_points
        FROM nhl_player_season_stats
        WHERE season = ? AND position IN ({placeholders})
        ORDER BY fantasy_points_espn DESC
        LIMIT 500
        """,
        [season, *skater_pos],
    ).df()


render_sport_compare_page(
    "nhl",
    label="NHL",
    caption="Compare **skaters to skaters** or **goalies to goalies** only.",
    load_rows=_load_nhl_rows,
)
