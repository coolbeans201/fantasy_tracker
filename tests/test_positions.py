"""Tests for fantasy position normalization."""

from src.positions import (
    COMPARE_GROUP_DST,
    COMPARE_GROUP_KICKER,
    COMPARE_GROUP_OFFENSE,
    OFFENSE_POSITIONS,
    coerce_leader_selection,
    compare_cohort,
    compare_cohorts_compatible,
    expand_position_filter,
    is_fantasy_skill_position,
    normalize_fantasy_position,
    normalize_leader_selection,
)


def test_fb_becomes_rb():
    assert normalize_fantasy_position("FB") == "RB"
    assert normalize_fantasy_position("rb") == "RB"
    assert normalize_fantasy_position("HB") == "RB"
    assert normalize_fantasy_position("K") == "K"


def test_defense_excluded():
    assert normalize_fantasy_position("LB") is None
    assert normalize_fantasy_position("CB") is None
    assert is_fantasy_skill_position("QB") is True
    assert is_fantasy_skill_position("K") is True


def test_leader_selection_defaults_to_offense():
    assert normalize_leader_selection([]) == OFFENSE_POSITIONS
    assert normalize_leader_selection(None) == OFFENSE_POSITIONS


def test_leader_selection_k_and_dst_alone_only():
    assert coerce_leader_selection(["K", "QB"], ["K"]) == ["QB"]
    assert coerce_leader_selection(["DST", "WR"], ["DST"]) == ["WR"]
    assert coerce_leader_selection(["QB", "RB", "K"], ["QB", "RB"]) == ["K"]
    assert coerce_leader_selection(["QB", "DST"], ["QB"]) == ["DST"]
    assert coerce_leader_selection(["DST", "QB"], ["DST"]) == ["QB"]
    assert coerce_leader_selection(["QB"], ["DST"]) == ["QB"]


def test_expand_rb_includes_fb_for_legacy_rows():
    assert expand_position_filter(["RB"]) == ["FB", "RB"]


def test_compare_cohorts():
    assert compare_cohort(position="QB") == COMPARE_GROUP_OFFENSE
    assert compare_cohort(position="RB") == COMPARE_GROUP_OFFENSE
    assert compare_cohort(position="K") == COMPARE_GROUP_KICKER
    assert compare_cohort(entity_id="dst:DEN", position="DST") == COMPARE_GROUP_DST
    assert compare_cohorts_compatible(COMPARE_GROUP_OFFENSE, COMPARE_GROUP_OFFENSE)
    assert compare_cohorts_compatible(COMPARE_GROUP_OFFENSE, COMPARE_GROUP_KICKER) is False
    assert compare_cohorts_compatible(COMPARE_GROUP_KICKER, COMPARE_GROUP_DST) is False
