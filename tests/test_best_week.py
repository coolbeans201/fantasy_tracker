"""Tests for preset-aligned best week."""

import pandas as pd

from src.analytics.best_week import best_week_by_season, overlay_preset_best_week


def test_best_week_by_season_picks_max_fp():
    weekly = pd.DataFrame(
        {
            "season": [2020, 2020, 2020],
            "week": [1, 2, 3],
            "fantasy_points": [10.0, 25.0, 15.0],
        }
    )
    best = best_week_by_season(weekly)
    assert len(best) == 1
    assert int(best.iloc[0]["best_week"]) == 2
    assert float(best.iloc[0]["best_week_fp"]) == 25.0


def test_overlay_replaces_ingest_columns():
    seasons = pd.DataFrame(
        {
            "season": [2020],
            "position": ["QB"],
            "fantasy_points": [100.0],
            "best_week": [1],
            "best_week_fp": [5.0],
        }
    )
    weekly = pd.DataFrame(
        {"season": [2020, 2020], "week": [1, 2], "fantasy_points": [5.0, 30.0]}
    )
    out = overlay_preset_best_week(seasons, weekly, "Half-PPR", dst=False)
    assert float(out.iloc[0]["best_week_fp"]) == 30.0
    assert int(out.iloc[0]["best_week"]) == 2
