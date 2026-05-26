"""NHL season leaders with per-team rows."""

from __future__ import annotations

import duckdb

from src.sports.nhl.queries import season_leaders


def test_season_leaders_team_filter_per_stint():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE nhl_player_season_stats (
            player_id VARCHAR, player_name VARCHAR, season INTEGER, position VARCHAR,
            team VARCHAR, games INTEGER, fantasy_points_espn DOUBLE,
            goals DOUBLE, assists DOUBLE, points DOUBLE, plus_minus DOUBLE,
            shots DOUBLE, hits DOUBLE, blocks DOUBLE,
            wins DOUBLE, saves DOUBLE, goals_against DOUBLE, shutouts DOUBLE,
            PRIMARY KEY (player_id, season, position, team)
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO nhl_player_season_stats VALUES
        (?, ?, 2024, 'C', ?, ?, ?, 0,0,0,0,0,0,0,0,0,0,0,0)
        """,
        [
            ("p1", "Traded Star", "TOR", 40, 80.0),
            ("p1", "Traded Star", "EDM", 35, 90.0),
        ],
    )
    all_rows = season_leaders(conn, 2024, "espn", min_games=1)
    assert len(all_rows) == 2

    tor = season_leaders(conn, 2024, "espn", min_games=1, team="TOR")
    assert len(tor) == 1
    assert tor.iloc[0]["team"] == "TOR"
    assert float(tor.iloc[0]["fantasy_points"]) == 80.0
