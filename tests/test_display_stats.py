"""Tests for position-aware stat column display."""

from src.stats_columns import display_stats_for_positions
from src.kicker_columns import KICKER_STAT_COLUMNS
from src.team_dst_columns import DST_STAT_COLUMNS


def test_offense_default_excludes_kicker_and_dst_stats():
    cols = display_stats_for_positions(["QB", "RB"])
    assert "pat_made" not in cols
    assert "points_allowed" not in cols
    assert "passing_yards" in cols


def test_kicker_only_shows_kicker_stats():
    cols = display_stats_for_positions(["K"])
    assert cols == list(KICKER_STAT_COLUMNS)


def test_dst_only_shows_dst_stats():
    cols = display_stats_for_positions(["DST"])
    assert cols == list(DST_STAT_COLUMNS)
