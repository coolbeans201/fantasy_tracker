"""MLB season leaders with per-team rows."""

from __future__ import annotations

import duckdb

from src.sports.mlb.queries import season_leaders


def test_season_leaders_team_filter_matches_single_stint():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE mlb_player_season_stats (
            player_id VARCHAR, player_name VARCHAR, season INTEGER, position VARCHAR,
            team VARCHAR, games INTEGER, fantasy_points_espn DOUBLE,
            runs DOUBLE, home_runs DOUBLE, rbi DOUBLE, stolen_bases DOUBLE,
            wins DOUBLE, strikeouts_pitch DOUBLE, saves DOUBLE, innings_pitched DOUBLE, era DOUBLE,
            walks DOUBLE DEFAULT 0, strikeouts_bat DOUBLE DEFAULT 0, batting_avg DOUBLE DEFAULT 0,
            whip DOUBLE DEFAULT 0,
            PRIMARY KEY (player_id, season, position, team)
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO mlb_player_season_stats VALUES
        (?, ?, 2024, 'OF', ?, ?, ?, 0,0,0,0,0,0,0,0,0,0,0,0,0)
        """,
        [
            ("p1", "Traded Star", "LAD", 60, 120.0),
            ("p1", "Traded Star", "NYY", 50, 90.0),
        ],
    )
    all_rows = season_leaders(conn, 2024, "espn", min_games=1)
    assert len(all_rows) == 2

    lad = season_leaders(conn, 2024, "espn", min_games=1, team="LAD")
    assert len(lad) == 1
    assert lad.iloc[0]["team"] == "LAD"
    assert float(lad.iloc[0]["fantasy_points"]) == 120.0
