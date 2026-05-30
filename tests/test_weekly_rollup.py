import pandas as pd

from src.sports.weekly_rollup import rollup_game_log_to_weeks


def test_rollup_monday_buckets_sum_fp():
    games = pd.DataFrame(
        [
            {
                "player_id": "p1",
                "season": 2025,
                "position": "PG",
                "game_date": "2025-01-06",
                "fantasy_points": 10.0,
            },
            {
                "player_id": "p1",
                "season": 2025,
                "position": "PG",
                "game_date": "2025-01-08",
                "fantasy_points": 15.0,
            },
            {
                "player_id": "p1",
                "season": 2025,
                "position": "PG",
                "game_date": "2025-01-13",
                "fantasy_points": 20.0,
            },
        ]
    )
    weeks = rollup_game_log_to_weeks(games, "nba").sort_values("week")
    assert len(weeks) == 2
    w1 = weeks.iloc[0]
    w2 = weeks.iloc[1]
    assert int(w1["games"]) == 2
    assert float(w1["fantasy_points"]) == 25.0
    assert float(w2["fantasy_points"]) == 20.0
