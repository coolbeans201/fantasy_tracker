"""Tests for peer-Z volume gates."""

import pandas as pd

from src.analytics.variance import qualifies_for_peer_z


def test_wr_gate_uses_targets_not_receptions():
    row = pd.Series(
        {
            "position": "WR",
            "games": 16,
            "targets": 55,
            "receptions": 20,
            "passing_attempts": 0,
            "carries": 0,
        }
    )
    assert qualifies_for_peer_z(row, min_games=8) is True

    low_targets = row.copy()
    low_targets["targets"] = 30
    assert qualifies_for_peer_z(low_targets, min_games=8) is False
