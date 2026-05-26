"""Compare cohort compatibility."""

from __future__ import annotations

import duckdb

from src.sports.compare_cohort import compare_cohorts_compatible


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
