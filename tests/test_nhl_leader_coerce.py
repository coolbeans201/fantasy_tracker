"""NHL season leaders position coercion (no skater/goalie mix)."""

from src.sports.nhl.positions import (
    GOALIE_POSITION,
    coerce_leader_selection,
    expand_leader_positions,
    is_goalie_only_selection,
    is_skater_only_selection,
    leader_position_options,
)


def test_leader_options_include_s_and_g_shortcuts():
    opts = leader_position_options()
    assert opts[0] == "S"
    assert GOALIE_POSITION in opts


def test_default_is_skaters_only():
    assert is_skater_only_selection(coerce_leader_selection([], []))
    assert not is_goalie_only_selection(coerce_leader_selection([], []))


def test_adding_goalie_drops_skaters():
    prev = ["C", "LW"]
    out = coerce_leader_selection(["C", "G"], prev)
    assert is_goalie_only_selection(out)
    assert "C" not in out


def test_adding_skater_drops_goalie():
    prev = ["G"]
    out = coerce_leader_selection(["G", "D"], prev)
    assert is_skater_only_selection(out)
    assert GOALIE_POSITION not in out


def test_expand_skater_shortcut():
    expanded = expand_leader_positions(["S"])
    assert "C" in expanded
    assert GOALIE_POSITION not in expanded


def test_expand_goalie_only():
    expanded = expand_leader_positions(["G"])
    assert expanded == ["G"]
