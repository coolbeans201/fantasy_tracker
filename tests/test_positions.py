"""Tests for fantasy position normalization."""

from src.positions import expand_position_filter, is_fantasy_skill_position, normalize_fantasy_position


def test_fb_becomes_rb():
    assert normalize_fantasy_position("FB") == "RB"
    assert normalize_fantasy_position("rb") == "RB"
    assert normalize_fantasy_position("HB") == "RB"


def test_defense_excluded():
    assert normalize_fantasy_position("LB") is None
    assert normalize_fantasy_position("CB") is None
    assert normalize_fantasy_position("K") is None
    assert is_fantasy_skill_position("QB") is True


def test_expand_rb_includes_fb_for_legacy_rows():
    assert expand_position_filter(["RB"]) == ["FB", "RB"]
