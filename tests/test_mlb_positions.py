"""MLB detailed position normalization."""

from src.sports.mlb.positions import (
    classify_pitcher_role,
    coerce_leader_selection,
    expand_leader_positions,
    normalize_mlb_field_position,
    normalize_mlb_position,
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


def test_resolve_batting_position_prefers_bref_dh():
    from src.sports.mlb.batting_position import resolve_batting_position

    assert (
        resolve_batting_position(
            bref_pos="DH",
            player_id="660271",
            api_by_id={"660271": "OF"},
        )
        == "DH"
    )


def test_resolve_batting_position_api_before_default():
    from src.sports.mlb.batting_position import resolve_batting_position

    assert (
        resolve_batting_position(
            bref_pos=None,
            player_id="123",
            api_by_id={"123": "CF"},
        )
        == "CF"
    )
    assert (
        resolve_batting_position(
            bref_pos=None,
            player_id="999",
            api_by_id={},
        )
        == "DH"
    )


def test_legacy_hitter_code_maps_to_dh_for_storage():
    assert normalize_mlb_field_position("H") == "DH"
    assert normalize_mlb_position("H") == "DH"
    assert normalize_mlb_position("hitter") == "DH"


def test_expand_legacy_hitter_filter():
    expanded = expand_leader_positions(["H"])
    assert "CF" in expanded
    assert "SP" not in expanded


def test_coerce_removing_h_does_not_expand_all_field_positions():
    assert coerce_leader_selection(["H"], []) == ["H"]
    assert coerce_leader_selection([], ["H"]) == []
    assert coerce_leader_selection(["CF"], ["H"]) == ["CF"]
