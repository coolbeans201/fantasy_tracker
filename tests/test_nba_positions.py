"""NBA player ID and position normalization."""

from src.sports.nba.player_positions import normalize_player_id
from src.sports.nba.positions import normalize_nba_position


def test_normalize_player_id_strips_float_suffix():
    assert normalize_player_id(2544.0) == "2544"
    assert normalize_player_id("2544.0") == "2544"
    assert normalize_player_id("1630162") == "1630162"


def test_normalize_nba_roster_labels():
    assert normalize_nba_position("PG") == "PG"
    assert normalize_nba_position("G-F") == "SG"
    assert normalize_nba_position("F-C") == "PF"
    assert normalize_nba_position("C") == "C"
    assert normalize_nba_position("Forward") == "SF"
