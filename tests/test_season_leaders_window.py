import pandas as pd

from src.db.queries import _aggregate_leader_window


def test_aggregate_leader_window_sums_across_seasons():
    per_season = pd.DataFrame(
        {
            "player_id": ["p1", "p1"],
            "player_name": ["Alice", "Alice"],
            "position": ["RB", "RB"],
            "team": ["KC", "KC"],
            "season": [2020, 2021],
            "games": [10, 12],
            "fantasy_points": [100.0, 120.0],
            "carries": [200, 220],
        }
    )
    out = _aggregate_leader_window(per_season)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["seasons_in_window"] == 2
    assert row["games"] == 22
    assert row["fantasy_points"] == 220.0
    assert row["carries"] == 420
    assert abs(row["fp_per_game"] - 220.0 / 22) < 0.01
