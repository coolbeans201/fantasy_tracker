"""Sport-scoped draft vs finish surprise."""

from unittest.mock import patch

import duckdb
import pandas as pd

from src.analytics.sport_surprise import (
    _collapse_mlb_qualified_by_role,
    _merge_ecr_with_stats,
    enrich_leaders_with_surprise_sport,
)


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


def test_mlb_collapses_duplicate_hitter_position_rows():
    qualified = pd.DataFrame(
        [
            {
                "player_id": "m1",
                "season": 2025,
                "position": "3B",
                "fantasy_points": 300.0,
                "games": 100,
                "plate_appearances": 250,
            },
            {
                "player_id": "m1",
                "season": 2025,
                "position": "UTIL",
                "fantasy_points": 50.0,
                "games": 20,
                "plate_appearances": 40,
            },
        ]
    )
    out = _collapse_mlb_qualified_by_role(qualified)
    assert len(out) == 1
    assert out.iloc[0]["position"] == "3B"
    assert float(out.iloc[0]["plate_appearances"]) == 290.0


def test_mlb_enrich_leaders_attach_by_hitter_role_not_field_spot():
    surprise_df = pd.DataFrame(
        [
            {
                "player_id": "m1",
                "position": "1B",
                "draft_ecr": 12,
                "finish_rank": 5,
                "rank_delta": 7,
                "surprise_qualified": True,
            }
        ]
    )
    leaders = pd.DataFrame(
        [{"player_id": "m1", "position": "3B", "fantasy_points": 400.0}]
    )
    with patch(
        "src.analytics.sport_surprise.season_has_rankings", return_value=True
    ):
        out = enrich_leaders_with_surprise_sport(
            duckdb.connect(":memory:"),
            "mlb",
            leaders,
            2025,
            "espn",
            surprise_df=surprise_df,
        )
    assert int(out.iloc[0]["draft_ecr"]) == 12


def test_mlb_ecr_merge_ignores_outfield_label_mismatch():
    """RF on stats + LF on ECR still attach (same hitter role)."""
    qualified = pd.DataFrame(
        [
            {
                "player_id": "592450",
                "season": 2025,
                "position": "RF",
                "fantasy_points": 531.0,
                "finish_rank": 1.0,
                "games": 140,
            },
        ]
    )
    ecr = pd.DataFrame(
        [
            {
                "player_id": "592450",
                "season": 2025,
                "position": "LF",
                "ecr_rank": 2,
                "player_name": "Aaron Judge",
            },
        ]
    )
    merged = _merge_ecr_with_stats(qualified, ecr, "mlb")
    assert len(merged) == 1
    row = merged.iloc[0]
    assert row["position"] == "RF"
    assert int(row["draft_ecr"]) == 2
    assert int(row["rank_delta"]) == 1


def test_mlb_two_way_merge_by_hitter_pitcher_role():
    qualified = pd.DataFrame(
        [
            {
                "player_id": "660271",
                "season": 2025,
                "position": "DH",
                "fantasy_points": 400.0,
                "finish_rank": 3.0,
                "games": 140,
            },
            {
                "player_id": "660271",
                "season": 2025,
                "position": "SP",
                "fantasy_points": 350.0,
                "finish_rank": 2.0,
                "games": 25,
            },
        ]
    )
    ecr = pd.DataFrame(
        [
            {
                "player_id": "660271",
                "season": 2025,
                "position": "LF",
                "ecr_rank": 8,
                "player_name": "Shohei Ohtani",
            },
            {
                "player_id": "660271",
                "season": 2025,
                "position": "SP",
                "ecr_rank": 5,
                "player_name": "Shohei Ohtani",
            },
        ]
    )
    merged = _merge_ecr_with_stats(qualified, ecr, "mlb")
    assert len(merged) == 2
    hitter = merged[merged["position"] == "DH"].iloc[0]
    pitcher = merged[merged["position"] == "SP"].iloc[0]
    assert int(hitter["draft_ecr"]) == 8
    assert int(pitcher["draft_ecr"]) == 5


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
