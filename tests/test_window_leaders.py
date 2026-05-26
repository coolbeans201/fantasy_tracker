"""Tests for sport window leader aggregation."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.sports.registry import season_leaders_window
from src.sports.window_leaders import aggregate_leader_window


def test_aggregate_leader_window_sums_fp_and_games():
    per_season = pd.DataFrame(
        [
            {
                "player_id": "1",
                "player_name": "A",
                "position": "PG",
                "team": "LAL",
                "season": 2022,
                "games": 40,
                "fantasy_points": 800.0,
            },
            {
                "player_id": "1",
                "player_name": "A",
                "position": "PG",
                "team": "LAL",
                "season": 2023,
                "games": 42,
                "fantasy_points": 900.0,
            },
        ]
    )
    out = aggregate_leader_window(per_season)
    assert len(out) == 1
    assert out.iloc[0]["games"] == 82
    assert out.iloc[0]["fantasy_points"] == 1700.0
    assert out.iloc[0]["seasons_in_window"] == 2


def test_season_leaders_window_mlb():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE mlb_player_season_stats (
            player_id VARCHAR, player_name VARCHAR, season INTEGER, position VARCHAR,
            team VARCHAR, games INTEGER, fantasy_points_espn DOUBLE,
            runs DOUBLE, home_runs DOUBLE, rbi DOUBLE, stolen_bases DOUBLE,
            wins DOUBLE, strikeouts_pitch DOUBLE, saves DOUBLE, innings_pitched DOUBLE, era DOUBLE
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO mlb_player_season_stats VALUES
        (?, ?, ?, 'OF', 'NYY', 100, 200.0, 0,0,0,0,0,0,0,0,0)
        """,
        [("p1", "Alice", 2022), ("p1", "Alice", 2023)],
    )
    df = season_leaders_window(conn, "mlb", [2022, 2023], "espn", min_games=50)
    assert len(df) == 1
    assert df.iloc[0]["fantasy_points"] == 400.0
