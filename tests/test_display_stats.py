"""Tests for position-aware stat column display."""

from src.sports.display_stats import display_stats_for_sport
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


def test_mlb_hitter_display_stats_omit_games_meta_column():
    """Games are shown via profile meta columns; avoid duplicate UI label."""
    cols = display_stats_for_sport("mlb", "1B")
    assert "games" not in cols
    assert "runs" in cols
