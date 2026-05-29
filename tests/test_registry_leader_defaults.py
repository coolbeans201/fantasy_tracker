"""Sport registry leader-selection defaults."""

from src.sports.registry import default_leader_selection
from src.sports.mlb.positions import FIELD_POSITIONS
from src.sports.nfl.positions import OFFENSE_POSITIONS
from src.sports.nhl.positions import SKATER_POSITIONS


def test_registry_nfl_default_matches_offense_positions():
    assert default_leader_selection("nfl") == list(OFFENSE_POSITIONS)


def test_registry_mlb_default_lists_field_positions():
    assert default_leader_selection("mlb") == list(FIELD_POSITIONS)
    assert "H" not in default_leader_selection("mlb")


def test_registry_nhl_default_lists_skater_positions():
    assert default_leader_selection("nhl") == list(SKATER_POSITIONS)
    assert "S" not in default_leader_selection("nhl")
