from src.sports.mlb.gamelogs import _extract_rows, fetch_player_gamelog_combined
import warnings


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
    assert out.iloc[0]["log_type"] == "hitting"
    assert float(out.iloc[0]["runs"]) == 1.0
    assert float(out.iloc[0]["home_runs"]) == 1.0
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
    assert out.iloc[0]["log_type"] == "pitching"
    assert float(out.iloc[0]["innings_pitched"]) == 6.0
    assert float(out.iloc[0]["fantasy_points_espn"]) == 28.0


def test_fetch_player_gamelog_combined_no_concat_future_warning(monkeypatch):
    hitting = _extract_rows(
        "660271",
        "Ohtani",
        2024,
        {
            "stats": [
                {
                    "group": {"displayName": "hitting"},
                    "splits": [
                        {
                            "date": "2024-04-01",
                            "game": {"gamePk": 1},
                            "team": {"abbreviation": "LAD"},
                            "opponent": {"abbreviation": "SD"},
                            "stat": {"runs": 1, "homeRuns": 0, "rbi": 0},
                        }
                    ],
                }
            ]
        },
    )
    pitching = _extract_rows(
        "660271",
        "Ohtani",
        2024,
        {
            "stats": [
                {
                    "group": {"displayName": "pitching"},
                    "splits": [
                        {
                            "date": "2024-04-02",
                            "game": {"gamePk": 2},
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
        },
    )

    def fake_fetch(_pid, _name, _year, *, is_pitcher: bool):
        return pitching if is_pitcher else hitting

    import src.sports.mlb.gamelogs as mod

    monkeypatch.setattr(mod, "fetch_player_gamelog", fake_fetch)
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        out = fetch_player_gamelog_combined("660271", "Ohtani", 2024, is_pitcher=True)
    assert len(out) == 2
    assert set(out["log_type"]) == {"hitting", "pitching"}

