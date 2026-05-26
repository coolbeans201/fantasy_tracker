"""NHL ingest consolidation: per-team stints."""

from __future__ import annotations

import pandas as pd

from src.sports.nhl.consolidate import consolidate_nhl_season_frame, drop_redundant_combined_team_rows
from src.sports.nhl.teams import is_combined_team_label, normalize_nhl_team


def test_normalize_nhl_team():
    assert normalize_nhl_team(" tbl ") == "TBL"
    assert is_combined_team_label("TOR,EDM")


def test_drop_combined_label_when_splits_exist():
    frame = pd.DataFrame(
        [
            {"player_id": "1", "season": 2024, "position": "C", "team": "TOR"},
            {"player_id": "1", "season": 2024, "position": "C", "team": "EDM"},
            {"player_id": "1", "season": 2024, "position": "C", "team": "TOR,EDM"},
        ]
    )
    out = drop_redundant_combined_team_rows(frame)
    assert set(out["team"]) == {"TOR", "EDM"}


def test_consolidate_keeps_separate_team_rows():
    frame = pd.DataFrame(
        [
            {
                "player_id": "p1",
                "player_name": "Trade Bait",
                "season": 2024,
                "position": "C",
                "team": "TOR",
                "games": 40,
                "goals": 10,
                "assists": 15,
                "points": 25,
                "plus_minus": 2,
                "shots": 80,
                "hits": 20,
                "blocks": 10,
                "wins": 0,
                "saves": 0,
                "goals_against": 0,
                "shutouts": 0,
                "fantasy_points_espn": 50.0,
            },
            {
                "player_id": "p1",
                "player_name": "Trade Bait",
                "season": 2024,
                "position": "C",
                "team": "EDM",
                "games": 35,
                "goals": 12,
                "assists": 18,
                "points": 30,
                "plus_minus": 5,
                "shots": 70,
                "hits": 15,
                "blocks": 8,
                "wins": 0,
                "saves": 0,
                "goals_against": 0,
                "shutouts": 0,
                "fantasy_points_espn": 55.0,
            },
        ]
    )
    out = consolidate_nhl_season_frame(frame)
    assert len(out) == 2
    assert set(out["team"]) == {"TOR", "EDM"}
