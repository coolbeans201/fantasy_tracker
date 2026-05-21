"""Tests for peer-Z volume gates."""

import pandas as pd

import numpy as np

from src.analytics.variance import compute_career_z, qualifies_for_peer_z


def test_wr_gate_uses_targets_not_receptions():
    row = pd.Series(
        {
            "position": "WR",
            "games": 16,
            "targets": 55,
            "receptions": 20,
            "passing_attempts": 0,
            "carries": 0,
        }
    )
    assert qualifies_for_peer_z(row, min_games=8) is True

    low_targets = row.copy()
    low_targets["targets"] = 30
    assert qualifies_for_peer_z(low_targets, min_games=8) is False


def test_career_z_skips_injury_short_seasons():
    df = pd.DataFrame(
        [
            {
                "season": 2007,
                "position": "QB",
                "games": 16,
                "passing_attempts": 500,
                "fantasy_points": 300.0,
            },
            {
                "season": 2008,
                "position": "QB",
                "games": 1,
                "passing_attempts": 10,
                "fantasy_points": 40.0,
            },
            {
                "season": 2009,
                "position": "QB",
                "games": 16,
                "passing_attempts": 520,
                "fantasy_points": 310.0,
            },
        ]
    )
    out = compute_career_z(df, min_games=8)
    assert np.isnan(out.loc[out["season"] == 2008, "career_z"].iloc[0])
    assert not np.isnan(out.loc[out["season"] == 2007, "career_z"].iloc[0])
    assert not np.isnan(out.loc[out["season"] == 2009, "career_z"].iloc[0])
