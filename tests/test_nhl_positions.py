"""NHL position normalization."""

from src.sports.nhl.positions import (
    expand_leader_positions,
    normalize_nhl_skater_position,
)


def test_position_codes():
    assert normalize_nhl_skater_position("C") == "C"
    assert normalize_nhl_skater_position("L") == "LW"
    assert normalize_nhl_skater_position("R") == "RW"
    assert normalize_nhl_skater_position("D") == "D"
    assert normalize_nhl_skater_position("LW") == "LW"


def test_expand_legacy_skater():
    expanded = expand_leader_positions(["S"])
    assert "C" in expanded
    assert "G" not in expanded
