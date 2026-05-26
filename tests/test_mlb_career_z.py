"""MLB career Z exclusions."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.sport_variance import compute_career_z_sport
from src.sports.mlb.seasons import MLB_COVID_SHORTENED_SEASON, mlb_career_z_excluded_season


def test_mlb_2020_excluded_from_career_z():
    assert mlb_career_z_excluded_season(MLB_COVID_SHORTENED_SEASON)
    assert not mlb_career_z_excluded_season(2019)


def test_compute_career_z_sport_skips_mlb_2020():
    df = pd.DataFrame(
        [
            {"season": 2019, "position": "OF", "games": 140, "fantasy_points": 200.0},
            {"season": MLB_COVID_SHORTENED_SEASON, "position": "OF", "games": 40, "fantasy_points": 120.0},
            {"season": 2021, "position": "OF", "games": 130, "fantasy_points": 210.0},
        ]
    )
    out = compute_career_z_sport(df, "mlb", min_games=1)
    assert np.isnan(out.loc[out["season"] == MLB_COVID_SHORTENED_SEASON, "career_z"].iloc[0])
    assert not np.isnan(out.loc[out["season"] == 2019, "career_z"].iloc[0])
    assert not np.isnan(out.loc[out["season"] == 2021, "career_z"].iloc[0])
