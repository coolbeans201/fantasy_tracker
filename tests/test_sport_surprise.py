"""Sport-scoped draft vs finish surprise."""

import pandas as pd

from src.analytics.sport_surprise import _merge_ecr_with_stats


def test_overall_ecr_converted_to_positional_draft_rank():
    """MLB-style overall ranks must not be compared directly to positional finish."""
    qualified = pd.DataFrame(
        [
            {
                "player_id": "a",
                "season": 2025,
                "position": "LF",
                "fantasy_points": 200.0,
                "finish_rank": 1.0,
                "games": 100,
            },
            {
                "player_id": "b",
                "season": 2025,
                "position": "LF",
                "fantasy_points": 150.0,
                "finish_rank": 2.0,
                "games": 100,
            },
        ]
    )
    ecr = pd.DataFrame(
        [
            {
                "player_id": "a",
                "season": 2025,
                "position": "LF",
                "ecr_rank": 1200,
                "player_name": "Late",
            },
            {
                "player_id": "b",
                "season": 2025,
                "position": "LF",
                "ecr_rank": 50,
                "player_name": "Early",
            },
        ]
    )
    merged = _merge_ecr_with_stats(qualified, ecr, "mlb")
    a = merged[merged["player_id"] == "a"].iloc[0]
    b = merged[merged["player_id"] == "b"].iloc[0]
    assert int(a["draft_ecr"]) == 2
    assert int(b["draft_ecr"]) == 1
    assert int(a["rank_delta"]) == 1
    assert int(b["rank_delta"]) == -1


def test_merge_ecr_positions_within_pg():
    qualified = pd.DataFrame(
        [
            {
                "player_id": "p1",
                "season": 2025,
                "position": "PG",
                "fantasy_points": 300.0,
                "finish_rank": 1.0,
                "games": 70,
            },
            {
                "player_id": "p2",
                "season": 2025,
                "position": "PG",
                "fantasy_points": 200.0,
                "finish_rank": 2.0,
                "games": 70,
            },
        ]
    )
    ecr = pd.DataFrame(
        [
            {
                "player_id": "p1",
                "season": 2025,
                "position": "PG",
                "ecr_rank": 147,
                "player_name": "Alpha",
            },
            {
                "player_id": "p2",
                "season": 2025,
                "position": "PG",
                "ecr_rank": 8,
                "player_name": "Beta",
            },
        ]
    )
    merged = _merge_ecr_with_stats(qualified, ecr, "nba")
    assert len(merged) == 2
    p1 = merged[merged["player_id"] == "p1"].iloc[0]
    p2 = merged[merged["player_id"] == "p2"].iloc[0]
    assert int(p1["draft_ecr"]) == 2
    assert int(p2["draft_ecr"]) == 1
    assert int(p1["finish_rank"]) == 1
    assert int(p1["rank_delta"]) == 1


def test_overall_ecr_converted_for_nhl_goalies():
    """NHL overall-style ECR ranks are re-ranked within position before merge."""
    qualified = pd.DataFrame(
        [
            {
                "player_id": "g1",
                "season": 2025,
                "position": "G",
                "fantasy_points": 250.0,
                "finish_rank": 1.0,
                "games": 60,
            },
            {
                "player_id": "g2",
                "season": 2025,
                "position": "G",
                "fantasy_points": 200.0,
                "finish_rank": 2.0,
                "games": 58,
            },
        ]
    )
    ecr = pd.DataFrame(
        [
            {
                "player_id": "g1",
                "season": 2025,
                "position": "G",
                "ecr_rank": 400,
                "player_name": "Late",
            },
            {
                "player_id": "g2",
                "season": 2025,
                "position": "G",
                "ecr_rank": 12,
                "player_name": "Early",
            },
        ]
    )
    merged = _merge_ecr_with_stats(qualified, ecr, "nhl")
    g1 = merged[merged["player_id"] == "g1"].iloc[0]
    g2 = merged[merged["player_id"] == "g2"].iloc[0]
    assert int(g1["draft_ecr"]) == 2
    assert int(g2["draft_ecr"]) == 1
    assert int(g1["rank_delta"]) == 1
    assert int(g2["rank_delta"]) == -1
