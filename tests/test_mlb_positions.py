"""MLB detailed position normalization."""

from src.sports.mlb.positions import (
    classify_pitcher_role,
    expand_leader_positions,
    normalize_mlb_field_position,
)


def test_field_positions():
    assert normalize_mlb_field_position("CF") == "CF"
    assert normalize_mlb_field_position("2B-SS") == "2B"
    assert normalize_mlb_field_position("LF/CF") == "LF"
    assert normalize_mlb_field_position("DH") == "DH"


def test_pitcher_roles():
    assert classify_pitcher_role(32, 32, 0) == "SP"
    assert classify_pitcher_role(60, 0, 25) == "RP"
    assert classify_pitcher_role(10, 6, 0) == "SP"


def test_expand_legacy_hitter_filter():
    expanded = expand_leader_positions(["H"])
    assert "CF" in expanded
    assert "SP" not in expanded
