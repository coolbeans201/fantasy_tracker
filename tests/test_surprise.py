"""Tests for ECR vs finish rank surprise."""

import pandas as pd

from src.analytics.surprise import (
    _ensure_player_id_column,
    assign_positional_ranks,
    top_surprise_slices,
)
from src.entities import make_dst_entity_id
from src.analytics.variance import add_volume_flags, qualifies_for_peer_z


def test_assign_positional_ranks():
    df = pd.DataFrame(
        [
            {"position": "RB", "fantasy_points": 200.0},
            {"position": "RB", "fantasy_points": 150.0},
            {"position": "WR", "fantasy_points": 180.0},
        ]
    )
    out = assign_positional_ranks(df)
    rb = out[out["position"] == "RB"].sort_values("finish_rank")
    assert rb.iloc[0]["finish_rank"] == 1
    assert rb.iloc[1]["finish_rank"] == 2


def test_rank_delta_outperform_vs_flop():
    row = pd.Series(
        {
            "position": "WR",
            "games": 16,
            "targets": 100,
            "passing_attempts": 0,
            "carries": 0,
        }
    )
    assert qualifies_for_peer_z(row, min_games=8) is True
    injured = row.copy()
    injured["games"] = 4
    assert qualifies_for_peer_z(injured, min_games=8) is False


def test_ensure_player_id_from_team_for_dst_leaders():
    df = pd.DataFrame(
        [{"team": "KC", "player_name": "Kansas City", "position": "DST", "fantasy_points": 120.0}]
    )
    out = _ensure_player_id_column(df)
    assert out.iloc[0]["player_id"] == make_dst_entity_id("KC")


def test_top_surprise_slices():
    df = pd.DataFrame(
        [
            {"player_name": "A", "rank_delta": 20, "surprise_qualified": True},
            {"player_name": "B", "rank_delta": -15, "surprise_qualified": True},
            {"player_name": "C", "rank_delta": 5, "surprise_qualified": True},
        ]
    )
    over, under = top_surprise_slices(df, n=1)
    assert over.iloc[0]["player_name"] == "A"
    assert under.iloc[0]["player_name"] == "B"
