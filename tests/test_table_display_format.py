"""Tests for UI table number formatting."""

import pandas as pd

from src.stats_columns import round_table_for_display


def test_season_stays_integer_not_float_display():
    df = pd.DataFrame({"season": [2020, 2021], "fantasy_points": [100.456, 200.789]})
    out = round_table_for_display(df)
    assert str(out["season"].dtype) == "Int64"
    assert int(out["season"].iloc[0]) == 2020
    assert float(out["fantasy_points"].iloc[0]) == 100.46


def test_counting_stats_are_integers():
    from src.stats_columns import rename_stats_for_display

    df = pd.DataFrame(
        {
            "passing_attempts": [319.0, 410.0],
            "passing_yards": [4023.0, 4500.0],
            "fantasy_points": [312.456, 280.1],
        }
    )
    out = rename_stats_for_display(df)
    assert str(out["Passing Attempts"].dtype) == "Int64"
    assert int(out["Passing Attempts"].iloc[0]) == 319
    assert float(out["Fantasy Points"].iloc[0]) == 312.46
