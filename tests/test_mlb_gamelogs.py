from src.sports.mlb.gamelogs import _extract_rows


def test_extract_rows_hitting_payload():
    payload = {
        "stats": [
            {
                "group": {"displayName": "hitting"},
                "splits": [
                    {
                        "date": "2024-04-01",
                        "game": {"gamePk": 12345},
                        "team": {"abbreviation": "NYY"},
                        "opponent": {"abbreviation": "BOS"},
                        "stat": {
                            "runs": 1,
                            "homeRuns": 1,
                            "rbi": 2,
                            "stolenBases": 0,
                            "baseOnBalls": 1,
                            "strikeOuts": 2,
                        },
                    }
                ],
            }
        ]
    }
    out = _extract_rows("592450", "Aaron Judge", 2024, payload)
    assert len(out) == 1
    assert out.iloc[0]["team"] == "NYY"
    assert out.iloc[0]["opponent"] == "BOS"
    assert float(out.iloc[0]["fantasy_points_espn"]) == 6.0


def test_extract_rows_pitching_payload():
    payload = {
        "stats": [
            {
                "group": {"displayName": "pitching"},
                "splits": [
                    {
                        "date": "2024-05-01",
                        "game": {"gamePk": 777},
                        "team": {"abbreviation": "LAD"},
                        "opponent": {"abbreviation": "SD"},
                        "stat": {
                            "wins": 1,
                            "strikeOuts": 8,
                            "saves": 0,
                            "inningsPitched": 6.0,
                            "era": 3.0,
                        },
                    }
                ],
            }
        ]
    }
    out = _extract_rows("605135", "Pitcher", 2024, payload)
    assert len(out) == 1
    assert float(out.iloc[0]["fantasy_points_espn"]) == 28.0
