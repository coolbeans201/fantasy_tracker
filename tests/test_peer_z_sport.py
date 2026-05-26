"""Tests for sport peer Z position cohorts."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.analytics.peer_z_sport import peer_z_score_sport
from src.analytics.sport_variance import add_volume_flags_sport, qualifies_for_peer_z_sport
from src.sports.peer_positions import positions_for_peer_grouping


def test_nba_peer_grouping_exact_position():
    assert positions_for_peer_grouping("nba", "PG-SG") == "PG"
    assert positions_for_peer_grouping("nba", "SF") == "SF"


def test_peer_z_pg_not_vs_pf():
    rows = [
        {"player_id": str(i), "position": "PG", "games": 82, "fantasy_points": 1800.0 + i * 5}
        for i in range(12)
    ]
    rows.append(
        {"player_id": "pf1", "position": "PF", "games": 82, "fantasy_points": 1900.0}
    )
    peer_df = pd.DataFrame(rows)
    peer_df = add_volume_flags_sport(peer_df, "nba", min_games=41)
    z_pg = peer_z_score_sport(2000.0, peer_df, "nba", "PG")
    assert z_pg is not None
    assert z_pg > 0


def test_min_games_excludes_bench():
    row = pd.Series({"position": "PG", "games": 10, "fantasy_points": 500.0})
    assert not qualifies_for_peer_z_sport(row, "nba", min_games=41)
