"""NBA season leaders position multiselect coercion."""

from src.sports.nba.positions import LEADER_POSITIONS, coerce_leader_selection


def test_default_is_all_positions():
    assert coerce_leader_selection([], []) == LEADER_POSITIONS


def test_partial_selection_preserved_when_deselecting():
    prev = list(LEADER_POSITIONS)
    out = coerce_leader_selection(["PG", "SG", "SF", "PF"], prev)
    assert out == ["PG", "SG", "SF", "PF"]


def test_single_position():
    assert coerce_leader_selection(["C"], ["PG", "SG"]) == ["C"]


def test_empty_after_user_clears_all():
    assert coerce_leader_selection([], list(LEADER_POSITIONS)) == []
