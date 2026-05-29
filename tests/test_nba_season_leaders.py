"""NBA season leaders query helpers."""

from __future__ import annotations

import duckdb

from src.sports.nba.queries import season_leaders


def test_season_leaders_position_filter():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE nba_player_season_stats (
            player_id VARCHAR, player_name VARCHAR, season INTEGER, position VARCHAR,
            team VARCHAR, games INTEGER, fantasy_points_espn DOUBLE,
            points DOUBLE, rebounds DOUBLE, assists DOUBLE, steals DOUBLE, blocks DOUBLE,
            turnovers DOUBLE, three_pointers DOUBLE,
            PRIMARY KEY (player_id, season)
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO nba_player_season_stats VALUES
        (?, ?, 2025, ?, 'BOS', 70, 400.0, 25, 5, 8, 1, 1, 3, 2),
        (?, ?, 2025, ?, 'LAL', 65, 350.0, 22, 4, 7, 1, 0, 2, 3)
        """,
        [
            ("pg1", "Point Guard", "PG", "sg1", "Swing Guard", "SG"),
        ],
    )
    all_rows = season_leaders(conn, 2025, "espn", min_games=1)
    assert len(all_rows) == 2

    pg_only = season_leaders(conn, 2025, "espn", positions=["PG"], min_games=1)
    assert len(pg_only) == 1
    assert pg_only.iloc[0]["position"] == "PG"


def test_season_leaders_team_filter():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE nba_player_season_stats (
            player_id VARCHAR, player_name VARCHAR, season INTEGER, position VARCHAR,
            team VARCHAR, games INTEGER, fantasy_points_espn DOUBLE,
            points DOUBLE, rebounds DOUBLE, assists DOUBLE, steals DOUBLE, blocks DOUBLE,
            turnovers DOUBLE, three_pointers DOUBLE,
            PRIMARY KEY (player_id, season)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO nba_player_season_stats VALUES
        ('p1', 'Star', 2025, 'SF', 'BOS', 70, 500.0, 28, 8, 5, 1, 1, 2, 3)
        """
    )
    bos = season_leaders(conn, 2025, "espn", min_games=1, team="BOS")
    assert len(bos) == 1
    assert bos.iloc[0]["team"] == "BOS"

    empty = season_leaders(conn, 2025, "espn", min_games=1, team="LAL")
    assert empty.empty
