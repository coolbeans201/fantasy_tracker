"""ESPN kicker and D/ST scoring."""

import pandas as pd

from src.scoring.special import (
    compute_dst_points,
    compute_kicker_points,
    dst_tier_bonus,
    points_allowed_bonus,
)


def test_kicker_distance_buckets():
    row = pd.DataFrame(
        [
            {
                "pat_made": 2,
                "fg_made_40_49": 1,
                "fg_made_50_59": 1,
                "fg_missed": 1,
            }
        ]
    )
    # 2 PAT + 4 + 5 - 1 = 10
    assert compute_kicker_points(row).iloc[0] == 10.0


def test_dst_points_allowed_tiers():
    assert points_allowed_bonus(0, {"0": 10, "1-6": 7, "35+": -4}) == 10
    assert points_allowed_bonus(10, {"0": 10, "1-6": 7, "35+": -4}) == 4
    assert points_allowed_bonus(35, {"0": 10, "1-6": 7, "35+": -4}) == -4


def test_dst_yards_allowed_tiers():
    tiers = {"0-99": 5, "100-199": 3, "200-299": 2, "550+": -7}
    assert dst_tier_bonus(80, tiers) == 5
    assert dst_tier_bonus(150, tiers) == 3
    assert dst_tier_bonus(250, tiers) == 2
    assert dst_tier_bonus(600, tiers) == -7


def test_dst_event_scoring():
    row = pd.DataFrame(
        [
            {
                "sacks": 3,
                "def_interceptions": 2,
                "def_touchdowns": 1,
                "points_allowed": 7,
            }
        ]
    )
    fp = compute_dst_points(row).iloc[0]
    # 3*1 + 2*2 + 6 + PA tier 7-13 = 4 -> 3+4+6+4 = 17
    assert fp == 17.0
