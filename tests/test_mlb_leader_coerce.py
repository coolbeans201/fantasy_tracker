"""MLB season leaders position coercion (no hitter/pitcher mix)."""

from src.sports.mlb.positions import (
    coerce_leader_selection,
    is_hitter_only_selection,
    is_pitcher_only_selection,
)


def test_default_is_hitters_only():
    assert is_hitter_only_selection(coerce_leader_selection([], []))
    assert not is_pitcher_only_selection(coerce_leader_selection([], []))


def test_adding_pitcher_drops_hitters():
    prev = ["CF", "1B"]
    out = coerce_leader_selection(["CF", "SP"], prev)
    assert is_pitcher_only_selection(out)
    assert "CF" not in out


def test_adding_hitter_drops_pitchers():
    prev = ["SP"]
    out = coerce_leader_selection(["SP", "OF"], prev)
    assert is_hitter_only_selection(out)
    assert "SP" not in out


def test_partial_hitter_selection_is_preserved():
    all_hitters = ["CF", "1B", "2B", "3B", "SS", "LF", "RF", "OF", "DH", "UTIL"]
    out = coerce_leader_selection(["CF", "DH"], all_hitters)
    assert out == ["CF", "DH"]


def test_deselecting_hitter_keeps_remaining():
    prev = ["CF", "1B", "2B"]
    out = coerce_leader_selection(["CF", "1B"], prev)
    assert out == ["CF", "1B"]


def test_legacy_h_and_p_are_exclusive():
    assert is_hitter_only_selection(coerce_leader_selection(["H"], []))
    assert is_pitcher_only_selection(coerce_leader_selection(["P"], []))
    out = coerce_leader_selection(["H", "P"], ["H"])
    assert is_pitcher_only_selection(out) or is_hitter_only_selection(out)
    assert not (is_pitcher_only_selection(out) and is_hitter_only_selection(out))
