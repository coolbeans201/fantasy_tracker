import pandas as pd

from src.sports.mlb.regular_season_games import apply_regular_season_games


def test_apply_regular_season_games_overlays_mlbam_match():
    frame = pd.DataFrame(
        [
            {
                "player_id": "660271",
                "team": "LAD",
                "games": 175,
                "position": "H",
            }
        ]
    )
    games_map = {("660271", "LAD"): 158}
    aliases = {"LAD": "LAD", "LOS ANGELES": "LAD"}
    out = apply_regular_season_games(
        frame, games_map, season=2025, aliases=aliases
    )
    assert int(out.iloc[0]["games"]) == 158


def test_apply_regular_season_games_resolves_city_team_label():
    frame = pd.DataFrame(
        [{"player_id": "660271", "team": "LOS ANGELES", "games": 175, "position": "H"}]
    )
    games_map = {("660271", "LAD"): 158}
    aliases = {"LOS ANGELES": "LAD", "LAD": "LAD"}
    out = apply_regular_season_games(
        frame, games_map, season=2025, aliases=aliases
    )
    assert int(out.iloc[0]["games"]) == 158


def test_apply_regular_season_games_caps_when_no_match():
    frame = pd.DataFrame(
        [{"player_id": "unknown", "team": "NYY", "games": 200, "position": "H"}]
    )
    out = apply_regular_season_games(frame, {}, season=2025)
    assert int(out.iloc[0]["games"]) == 162
