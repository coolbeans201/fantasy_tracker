"""NBA draft ECR positional sanity checks."""

import pandas as pd

from src.analytics.surprise import assign_positional_ecr_ranks, ecr_ranks_look_overall


def test_ecr_ranks_look_overall_detects_high_ranks():
    draft = pd.DataFrame(
        [
            {"player_id": "1", "position": "PG", "ecr_rank": 147},
            {"player_id": "2", "position": "PG", "ecr_rank": 8},
        ]
    )
    assert ecr_ranks_look_overall(draft) is True


def test_assign_positional_ecr_ranks_compresses_overall_style():
    draft = pd.DataFrame(
        [
            {"player_id": "1", "position": "PG", "ecr_rank": 147},
            {"player_id": "2", "position": "PG", "ecr_rank": 8},
        ]
    )
    out = assign_positional_ecr_ranks(draft)
    best = out[out["player_id"] == "2"].iloc[0]["ecr_rank"]
    worst = out[out["player_id"] == "1"].iloc[0]["ecr_rank"]
    assert int(best) == 1
    assert int(worst) == 2
