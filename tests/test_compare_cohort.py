"""Compare cohort compatibility."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.sports.compare_cohort import (
    compare_cohorts_compatible,
    prepare_compare_season_rows,
)


def test_mlb_hitter_vs_pitcher_blocked():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE mlb_player_season_stats (
            player_id VARCHAR, season INTEGER, position VARCHAR
        )
        """
    )
    conn.execute(
        "INSERT INTO mlb_player_season_stats VALUES ('h', 2024, 'OF'), ('p', 2024, 'SP')"
    )
    ok, msg = compare_cohorts_compatible(
        "mlb",
        None,
        None,
        conn=conn,
        player_a="h",
        player_b="p",
        season=2024,
    )
    assert not ok
    assert msg and "hitters" in msg.lower()


def test_mlb_two_way_hitter_compare_allowed():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE mlb_player_season_stats (
            player_id VARCHAR, season INTEGER, position VARCHAR
        )
        """
    )
    conn.execute(
        "INSERT INTO mlb_player_season_stats VALUES "
        "('tw', 2024, 'OF'), ('tw', 2024, 'SP'), ('h', 2024, '1B')"
    )
    ok, _ = compare_cohorts_compatible(
        "mlb",
        None,
        None,
        conn=conn,
        player_a="tw",
        player_b="h",
        season=2024,
        cohort_hint="hitter",
    )
    assert ok


def test_prepare_compare_drops_pitching_rows_for_hitters():
    df = pd.DataFrame(
        [
            {
                "player_id": "tw",
                "season": 2024,
                "position": "DH",
                "team": "LAD",
                "games": 100,
                "runs": 80,
                "home_runs": 40,
                "rbi": 80,
                "stolen_bases": 10,
                "walks": 50,
                "strikeouts_bat": 100,
                "fantasy_points": 200.0,
            },
            {
                "player_id": "tw",
                "season": 2024,
                "position": "SP",
                "team": "LAD",
                "games": 10,
                "wins": 5,
                "strikeouts_pitch": 50,
                "innings_pitched": 60,
                "fantasy_points": 150.0,
            },
            {
                "player_id": "tw",
                "season": 2023,
                "position": "DH",
                "team": "LAA",
                "games": 90,
                "runs": 70,
                "home_runs": 35,
                "rbi": 70,
                "stolen_bases": 15,
                "walks": 40,
                "strikeouts_bat": 90,
                "fantasy_points": 180.0,
            },
        ]
    )
    out = prepare_compare_season_rows(df, "mlb", cohort_hint="hitter")
    assert len(out) == 2
    from src.sports.mlb.positions import is_pitcher_position

    assert not out["position"].map(is_pitcher_position).any()
    assert set(out["season"].astype(int)) == {2023, 2024}
