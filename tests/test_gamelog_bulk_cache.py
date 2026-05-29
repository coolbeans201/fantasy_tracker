import pandas as pd

from src.sports.gamelog_bulk import _gamelog_cache_missing_box_scores


def test_mlb_cache_missing_box_scores_detects_null_stat_columns():
    frame = pd.DataFrame(
        [
            {
                "game_id": "1",
                "log_type": "hitting",
                "runs": None,
                "home_runs": None,
                "fantasy_points_espn": 5.0,
            }
        ]
    )
    assert _gamelog_cache_missing_box_scores(frame, "mlb") is True


def test_mlb_cache_with_stats_is_not_stale():
    frame = pd.DataFrame(
        [{"game_id": "1", "log_type": "hitting", "runs": 1.0, "home_runs": 0.0}]
    )
    assert _gamelog_cache_missing_box_scores(frame, "mlb") is False


def test_nhl_cache_zero_saves_with_goals_against_is_stale():
    frame = pd.DataFrame(
        [
            {
                "game_id": "1",
                "log_type": "goalie",
                "saves": 0.0,
                "goals_against": 2.0,
            }
        ]
    )
    assert _gamelog_cache_missing_box_scores(frame, "nhl") is True
