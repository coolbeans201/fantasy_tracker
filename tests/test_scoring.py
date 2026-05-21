"""Unit tests for fantasy scoring."""

import pandas as pd

from src.scoring.calc import compute_fantasy_points, load_presets


def test_standard_qb_week():
    presets = load_presets()
    assert "standard" in presets
    row = pd.DataFrame(
        [
            {
                "passing_yards": 300,
                "passing_tds": 2,
                "interceptions": 1,
                "rushing_yards": 20,
                "rushing_tds": 0,
                "receptions": 0,
                "receiving_yards": 0,
                "receiving_tds": 0,
                "fumbles_lost": 0,
            }
        ]
    )
    # 300*0.04 + 8 + (-2) + 2 = 12 + 8 - 2 + 2 = 20
    fp = compute_fantasy_points(row, "standard").iloc[0]
    assert fp == 20.0


def test_half_ppr_reception():
    row = pd.DataFrame([{"receptions": 10, "receiving_yards": 100, "receiving_tds": 1}])
    fp = compute_fantasy_points(row, "half_ppr").iloc[0]
    # 10 + 10 + 6 = 26
    assert fp == 26.0
