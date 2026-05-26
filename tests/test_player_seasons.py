"""Tests for per-player and compare season year lists."""

from __future__ import annotations

import duckdb

from src.sports.player_seasons import (
    compare_shared_seasons,
    compare_union_seasons,
    player_seasons_available,
)


def _seed_mlb(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE mlb_player_season_stats (
            player_id VARCHAR,
            player_name VARCHAR,
            season INTEGER,
            position VARCHAR,
            team VARCHAR,
            games INTEGER,
            fantasy_points_espn DOUBLE
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO mlb_player_season_stats VALUES (?, ?, ?, 'OF', 'NYY', 10, 100.0)
        """,
        [
            ("p1", "Alice", 2022),
            ("p1", "Alice", 2023),
            ("p2", "Bob", 2021),
            ("p2", "Bob", 2023),
        ],
    )


def test_player_seasons_available_newest_first():
    conn = duckdb.connect(":memory:")
    _seed_mlb(conn)
    assert player_seasons_available(conn, "mlb", "p1") == [2023, 2022]


def test_compare_union_and_shared():
    conn = duckdb.connect(":memory:")
    _seed_mlb(conn)
    assert compare_union_seasons(conn, "mlb", "p1", "p2") == [2023, 2022, 2021]
    assert compare_shared_seasons(conn, "mlb", "p1", "p2") == [2023]
