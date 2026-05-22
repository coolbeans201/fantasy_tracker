"""Tests for derived metrics."""

import pandas as pd

from src.analytics.metrics import add_fp_per_game, count_prime_seasons, peak_season_year


def test_fp_per_game():
    df = pd.DataFrame({"games": [16, 8], "fantasy_points": [320.0, 80.0]})
    out = add_fp_per_game(df)
    assert out["fp_per_game"].iloc[0] == 20.0
    assert out["fp_per_game"].iloc[1] == 10.0


def test_prime_and_peak():
    career = pd.DataFrame(
        {
            "season": [2020, 2021, 2022],
            "fantasy_points": [100.0, 200.0, 150.0],
            "peer_qualified": [True, True, True],
            "career_z": [0.5, 1.5, 0.0],
        }
    )
    assert count_prime_seasons(career) == 1
    assert peak_season_year(career) == 2021
