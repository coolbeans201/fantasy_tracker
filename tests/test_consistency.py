"""Tests for weekly consistency metrics."""

import pandas as pd

from src.analytics.consistency import consistency_from_weekly, week_boom_bust_tags


def test_consistency_boom_bust_rates():
    weekly = pd.DataFrame({"fantasy_points": [5.0, 10.0, 15.0, 20.0]})
    metrics = consistency_from_weekly(weekly, p25=7.5, p75=17.5)
    assert metrics["weekly_std"] is not None
    assert metrics["boom_rate"] == 0.25
    assert metrics["bust_rate"] == 0.25
    assert metrics["worst_week_fp"] == 5.0


def test_week_boom_bust_tags():
    weekly = pd.DataFrame({"fantasy_points": [5.0, 10.0, 15.0, 20.0]})
    tags = week_boom_bust_tags(weekly, p25=7.5, p75=17.5)
    assert tags.tolist() == ["Bust", "", "", "Boom"]
