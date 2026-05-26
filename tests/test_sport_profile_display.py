"""Sport profile display helpers."""

from __future__ import annotations

import pandas as pd

from app.sport_profile_display import format_profile_table, profile_export_columns
from src.sports.display_stats import display_stats_for_sport


def test_profile_export_columns_mlb_splits_hitter_and_pitcher_stats():
    career = pd.DataFrame(
        [
            {
                "season": 2024,
                "team": "LAD",
                "position": "OF",
                "games": 50,
                "fantasy_points": 100.0,
                "fp_per_game": 2.0,
                "runs": 30,
                "home_runs": 10,
                "rbi": 25,
                "stolen_bases": 5,
                "wins": 0,
                "strikeouts_pitch": 0,
                "saves": 0,
                "innings_pitched": 0,
                "era": 0,
            },
            {
                "season": 2024,
                "team": "LAD",
                "position": "SP",
                "games": 10,
                "fantasy_points": 80.0,
                "fp_per_game": 8.0,
                "runs": 0,
                "home_runs": 0,
                "rbi": 0,
                "stolen_bases": 0,
                "wins": 5,
                "strikeouts_pitch": 60,
                "saves": 0,
                "innings_pitched": 50.0,
                "era": 3.2,
            },
        ]
    )
    cols = profile_export_columns("mlb", career)
    assert "runs" in cols
    assert "wins" in cols
    assert "player_id" not in cols


def test_format_profile_table_sp_row_omits_hitter_stats_and_ids():
    row = pd.Series(
        {
            "player_id": "669456",
            "player_name": "Shane Bieber",
            "season": 2020,
            "team": "CLE",
            "position": "SP",
            "games": 12,
            "fantasy_points": 391.7,
            "fp_per_game": 32.6,
            "runs": 0,
            "home_runs": 0,
            "wins": 8,
            "strikeouts_pitch": 122,
            "innings_pitched": 77.1,
            "era": 1.63,
        }
    )
    stat_cols = display_stats_for_sport("mlb", "SP")
    detail_cols = [
        c
        for c in [
            "season",
            "team",
            "position",
            "games",
            "fantasy_points",
            "fp_per_game",
        ]
        + stat_cols
        if c in row.index
    ]
    shown = format_profile_table(pd.DataFrame([row]), columns=detail_cols)
    labels = list(shown.columns)
    assert "player_id" not in labels
    assert "Player" not in labels
    assert "Runs" not in labels
    assert "Wins" in labels
    assert "Strikeouts (Pitching)" in labels
