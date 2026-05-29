"""Regular-season filters for game-log ingest."""

from __future__ import annotations

import pandas as pd

from src.sports.mlb.gamelogs import _extract_rows
from src.sports.season_type import (
    filter_nba_gamelog_frame,
    filter_nhl_gamelog_games,
    is_mlb_regular_season_split,
)


def test_is_mlb_regular_season_split():
    assert is_mlb_regular_season_split({"game": {"gameType": "R", "gamePk": 1}})
    assert not is_mlb_regular_season_split({"game": {"gameType": "P", "gamePk": 2}})


def test_extract_rows_skips_postseason():
    payload = {
        "stats": [
            {
                "group": {"displayName": "hitting"},
                "splits": [
                    {
                        "date": "2024-10-01",
                        "game": {"gamePk": 1, "gameType": "R"},
                        "team": {"abbreviation": "LAD"},
                        "opponent": {"abbreviation": "NYM"},
                        "stat": {"runs": 1},
                    },
                    {
                        "date": "2024-10-15",
                        "game": {"gamePk": 2, "gameType": "P"},
                        "team": {"abbreviation": "LAD"},
                        "opponent": {"abbreviation": "NYM"},
                        "stat": {"runs": 0},
                    },
                ],
            }
        ]
    }
    out = _extract_rows("660271", "Ohtani", 2024, payload)
    assert len(out) == 1
    assert out.iloc[0]["game_id"] == "1"


def test_filter_nba_gamelog_frame():
    raw = pd.DataFrame(
        {
            "SEASON_TYPE": ["Regular Season", "Playoffs"],
            "GAME_ID": ["1", "2"],
        }
    )
    out = filter_nba_gamelog_frame(raw)
    assert len(out) == 1
    assert out.iloc[0]["GAME_ID"] == "1"


def test_filter_nhl_gamelog_games():
    games = [
        {"gameId": "a", "gameType": 2},
        {"gameId": "b", "gameType": 3},
    ]
    kept = filter_nhl_gamelog_games(games)
    assert len(kept) == 1
    assert kept[0]["gameId"] == "a"
