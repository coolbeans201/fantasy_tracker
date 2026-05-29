"""Regular-season MLB season stat overlay (exclude postseason from BRef totals)."""

import pandas as pd

from src.sports.mlb.regular_season_games import (
    _parse_hitting_overlay,
    apply_regular_season_overlay,
)


def test_parse_hitting_overlay_maps_api_fields():
    stat = {
        "gamesPlayed": 154,
        "plateAppearances": 620,
        "runs": 90,
        "homeRuns": 60,
        "rbi": 100,
        "stolenBases": 5,
        "baseOnBalls": 70,
        "strikeOuts": 140,
        "avg": ".298",
    }
    out = _parse_hitting_overlay(stat)
    assert out["games"] == 154
    assert out["home_runs"] == 60
    assert abs(out["batting_avg"] - 0.298) < 0.001


def test_apply_regular_season_overlay_replaces_postseason_inflated_hr():
    frame = pd.DataFrame(
        [
            {
                "player_id": "663728",
                "team": "SEA",
                "games": 170,
                "plate_appearances": 650,
                "runs": 100,
                "home_runs": 65,
                "rbi": 100,
                "stolen_bases": 0,
                "walks": 80,
                "strikeouts_bat": 150,
                "batting_avg": 0.3,
                "fantasy_points_espn": 999.0,
            }
        ]
    )
    overlay = pd.DataFrame(
        [
            {
                "player_id": "663728",
                "team": "SEA",
                "games": 154,
                "plate_appearances": 620,
                "runs": 90,
                "home_runs": 60,
                "rbi": 95,
                "stolen_bases": 5,
                "walks": 70,
                "strikeouts_bat": 140,
                "batting_avg": 0.298,
            }
        ]
    )
    out = apply_regular_season_overlay(
        frame, overlay, season=2025, group="hitting", aliases={"SEA": "SEA"}
    )
    assert int(out.iloc[0]["home_runs"]) == 60
    assert int(out.iloc[0]["games"]) == 154
    assert float(out.iloc[0]["fantasy_points_espn"]) != 999.0
