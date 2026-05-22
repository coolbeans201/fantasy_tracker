"""Tests for peer Z helpers."""

import pandas as pd

from src.analytics.peer_z import add_peer_z_season_column, peer_z_score
from src.analytics.variance import add_volume_flags, qualifies_for_peer_z
from src.positions import DST_POSITION


def test_kicker_volume_gate():
    row = pd.Series({"position": "K", "games": 10, "passing_attempts": 0, "targets": 0})
    assert qualifies_for_peer_z(row, min_games=8) is True
    short = row.copy()
    short["games"] = 5
    assert qualifies_for_peer_z(short, min_games=8) is False


def test_dst_always_peer_qualified():
    row = pd.Series({"position": DST_POSITION, "games": 17})
    assert qualifies_for_peer_z(row, min_games=8) is True


def test_dst_peer_z_uses_full_cohort():
    rows = [
        {"position": DST_POSITION, "fantasy_points": 50.0 + i * 10, "games": 17}
        for i in range(12)
    ]
    df = pd.DataFrame(rows)
    out = add_peer_z_season_column(df, dst_cohort=True)
    assert out["peer_z_season"].notna().all()
    top = out.loc[out["fantasy_points"] == out["fantasy_points"].max(), "peer_z_season"].iloc[0]
    assert top > 0


def test_peer_z_score_offense():
    peer_df = pd.DataFrame(
        [
            {"position": "RB", "games": 16, "carries": 200, "fantasy_points": 100.0},
            {"position": "RB", "games": 16, "carries": 180, "fantasy_points": 80.0},
        ]
        * 6
    )
    peer_df = add_volume_flags(peer_df, min_games=8)
    z = peer_z_score(150.0, peer_df, "RB", min_peers=5)
    assert z is not None and z > 0
