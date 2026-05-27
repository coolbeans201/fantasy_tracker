import pandas as pd

from src.sports.player_career import sort_career_rows


def test_sort_career_rows_chronological():
    df = pd.DataFrame(
        {
            "season": [2024, 2022, 2023],
            "team": ["BOS", "BOS", "BOS"],
            "fantasy_points": [100, 80, 90],
        }
    )
    out = sort_career_rows(df)
    assert out["season"].tolist() == [2022, 2023, 2024]
