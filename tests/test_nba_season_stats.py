"""NBA season counting stats from LeagueDash."""

from __future__ import annotations

import pandas as pd

from src.sports.nba.season_stats import LEAGUE_DASH_PER_MODE, counting_stats_from_league_dash


def test_league_dash_uses_totals_mode():
    assert LEAGUE_DASH_PER_MODE == "Totals"


def test_counting_stats_are_integer_season_totals():
    raw = pd.DataFrame(
        {
            "PTS": [2072.0],
            "REB": [889.0],
            "AST": [714.0],
            "STL": [126.0],
            "BLK": [42.0],
            "TOV": [231.0],
            "FG3M": [140.0],
            "GP": [70],
        }
    )
    stats = counting_stats_from_league_dash(raw)
    assert stats["points"].iloc[0] == 2072
    assert stats["rebounds"].iloc[0] == 889
    assert stats["games"].iloc[0] == 70
    assert str(stats["points"].dtype) == "int64"


def test_per_game_values_are_not_multiplied():
    """Regression: PerGame PTS * GP produced fractional fake totals."""
    raw = pd.DataFrame(
        {
            "PTS": [30.1],
            "REB": [11.9],
            "AST": [6.5],
            "STL": [0.9],
            "BLK": [1.2],
            "TOV": [3.1],
            "FG3M": [0.2],
            "GP": [67],
        }
    )
    stats = counting_stats_from_league_dash(raw)
    # Totals mode would send real totals; if mis-ingested as per-game, values stay wrong
    # but must at least be integers (rounded), not 30.1 * 67 style decimals in DB.
    assert stats["points"].iloc[0] == 30
    assert float(stats["points"].iloc[0]).is_integer()
