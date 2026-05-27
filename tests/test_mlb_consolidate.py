"""MLB ingest consolidation: per-team stints, no combined 2TM rows when splits exist."""

from __future__ import annotations

import pandas as pd

from src.sports.mlb.consolidate import consolidate_mlb_season_frame, drop_redundant_summary_team_rows
from src.sports.mlb.teams import is_summary_team, normalize_mlb_team


def test_summary_team_detection():
    assert is_summary_team("2TM")
    assert is_summary_team("3TM")
    assert is_summary_team("tot")
    assert not is_summary_team("LAD")
    assert normalize_mlb_team(" lad ") == "LAD"


def test_drop_2tm_when_team_splits_exist():
    frame = pd.DataFrame(
        [
            {"player_id": "p1", "season": 2024, "position": "OF", "team": "LAD", "games": 50},
            {"player_id": "p1", "season": 2024, "position": "OF", "team": "NYY", "games": 40},
            {"player_id": "p1", "season": 2024, "position": "OF", "team": "2TM", "games": 90},
        ]
    )
    out = drop_redundant_summary_team_rows(frame)
    assert set(out["team"]) == {"LAD", "NYY"}


def test_consolidate_keeps_separate_team_rows():
    frame = pd.DataFrame(
        [
            {
                "player_id": "p1",
                "player_name": "Test Player",
                "season": 2024,
                "position": "OF",
                "team": "LAD",
                "games": 50,
                "plate_appearances": 220,
                "runs": 30,
                "home_runs": 10,
                "rbi": 25,
                "stolen_bases": 5,
                "walks": 0,
                "strikeouts_bat": 0,
                "batting_avg": 0.28,
                "wins": 0,
                "strikeouts_pitch": 0,
                "saves": 0,
                "innings_pitched": 0,
                "era": 0,
                "whip": 0,
                "fantasy_points_espn": 100.0,
            },
            {
                "player_id": "p1",
                "player_name": "Test Player",
                "season": 2024,
                "position": "OF",
                "team": "NYY",
                "games": 40,
                "plate_appearances": 180,
                "runs": 20,
                "home_runs": 5,
                "rbi": 15,
                "stolen_bases": 2,
                "walks": 0,
                "strikeouts_bat": 0,
                "batting_avg": 0.25,
                "wins": 0,
                "strikeouts_pitch": 0,
                "saves": 0,
                "innings_pitched": 0,
                "era": 0,
                "whip": 0,
                "fantasy_points_espn": 80.0,
            },
            {
                "player_id": "p1",
                "player_name": "Test Player",
                "season": 2024,
                "position": "OF",
                "team": "2TM",
                "games": 90,
                "plate_appearances": 400,
                "runs": 50,
                "home_runs": 15,
                "rbi": 40,
                "stolen_bases": 7,
                "walks": 0,
                "strikeouts_bat": 0,
                "batting_avg": 0.27,
                "wins": 0,
                "strikeouts_pitch": 0,
                "saves": 0,
                "innings_pitched": 0,
                "era": 0,
                "whip": 0,
                "fantasy_points_espn": 180.0,
            },
        ]
    )
    out = consolidate_mlb_season_frame(frame)
    assert len(out) == 2
    assert set(out["team"]) == {"LAD", "NYY"}
    lad = out[out["team"] == "LAD"].iloc[0]
    assert int(lad["games"]) == 50
    assert float(lad["runs"]) == 30
