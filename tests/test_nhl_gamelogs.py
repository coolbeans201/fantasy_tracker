import json

import requests

from src.sports.game_logs import enrich_nhl_game_log_rows, filter_game_log_for_profile
from src.sports.nhl.gamelogs import _games_to_frame, fetch_player_gamelog


class _Resp:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return json.loads(json.dumps(self._payload))


def test_fetch_player_gamelog_parses_skater_payload(monkeypatch):
    payload = {
        "gameLog": [
            {
                "gameId": 2024020001,
                "gameDate": "2024-10-04",
                "teamAbbrev": "TOR",
                "opponentAbbrev": "MTL",
                "goals": 1,
                "assists": 2,
                "points": 3,
                "shots": 4,
            }
        ]
    }

    def fake_get(*_args, **_kwargs):
        return _Resp(payload)

    monkeypatch.setattr(requests, "get", fake_get)
    out = fetch_player_gamelog("8478402", "Skater", 2025, is_goalie=False)
    assert len(out) == 1
    assert out.iloc[0]["log_type"] == "skater"
    assert out.iloc[0]["team"] == "TOR"
    assert float(out.iloc[0]["fantasy_points_espn"]) == 9.0


def test_games_to_frame_goalie():
    games = [
        {
            "gameId": 2024020099,
            "gameDate": "2024-11-01",
            "teamAbbrev": "BOS",
            "opponentAbbrev": "NYR",
            "shotsAgainst": 28,
            "goalsAgainst": 2,
            "decision": "W",
        }
    ]
    out = _games_to_frame("8477492", "Goalie", 2025, games, is_goalie=True)
    assert len(out) == 1
    assert out.iloc[0]["log_type"] == "goalie"
    assert float(out.iloc[0]["wins"]) == 1.0
    assert float(out.iloc[0]["saves"]) == 26.0
    assert float(out.iloc[0]["goals_against"]) == 2.0
    assert float(out.iloc[0]["fantasy_points_espn"]) == 7.6


def test_games_to_frame_goalie_uses_shots_against_when_saves_missing():
    games = [
        {
            "gameId": 1,
            "gameDate": "2024-10-01",
            "teamAbbrev": "WPG",
            "opponentAbbrev": "EDM",
            "shotsAgainst": 30,
            "goalsAgainst": 0,
            "decision": "W",
            "shutouts": 1,
        }
    ]
    out = _games_to_frame("1", "Goalie", 2025, games, is_goalie=True)
    assert float(out.iloc[0]["saves"]) == 30.0
    assert float(out.iloc[0]["shutouts"]) == 1.0


def test_filter_nhl_goalie_game_log():
    games = enrich_nhl_game_log_rows(
        _games_to_frame(
            "1",
            "G",
            2025,
            [
                {
                    "gameId": 1,
                    "gameDate": "2024-10-01",
                    "teamAbbrev": "BOS",
                    "opponentAbbrev": "NYR",
                    "shotsAgainst": 30,
                    "goalsAgainst": 1,
                    "decision": "W",
                }
            ],
            is_goalie=True,
        )
    )
    out = filter_game_log_for_profile(games, "nhl", "G")
    assert len(out) == 1
    assert out.iloc[0]["log_type"] == "goalie"
