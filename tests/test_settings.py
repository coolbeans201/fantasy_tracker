"""Settings defaults."""

from src.settings import get_min_games_default


def test_min_games_default_by_sport():
    assert get_min_games_default("nfl") == 8
    assert get_min_games_default("mlb") == 200
    assert get_min_games_default("nba") == 41
    assert get_min_games_default("nhl") == 41
