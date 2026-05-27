import json

import requests

from src.sports.nhl.gamelogs import fetch_player_gamelog


class _Resp:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return json.loads(json.dumps(self._payload))


def test_fetch_player_gamelog_parses_payload(monkeypatch):
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
    out = fetch_player_gamelog("8478402", "Skater", 2025)
    assert len(out) == 1
    assert out.iloc[0]["team"] == "TOR"
    assert out.iloc[0]["opponent"] == "MTL"
    assert float(out.iloc[0]["fantasy_points_espn"]) == 9.0
