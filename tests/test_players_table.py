"""Players index rebuilt from all seasons."""

import duckdb

from src.db.maintenance import players_table_needs_rebuild, rebuild_players_table


def test_rebuild_players_includes_all_season_player_ids():
    conn = duckdb.connect()
    conn.execute(
        """
        CREATE TABLE season_stats (
            player_id VARCHAR,
            player_name VARCHAR,
            season INTEGER,
            position VARCHAR
        );
        CREATE TABLE players (sport VARCHAR, player_id VARCHAR, player_name VARCHAR,
            position VARCHAR, last_season INTEGER, PRIMARY KEY (sport, player_id));
        INSERT INTO season_stats VALUES
            ('luck', 'Andrew Luck', 2018, 'QB'),
            ('luck', 'Andrew Luck', 2017, 'QB'),
            ('active', 'Active Player', 2025, 'WR');
        INSERT INTO players VALUES ('nfl', 'active', 'Active Player', 'WR', 2025);
        """
    )
    assert players_table_needs_rebuild(conn) is True
    rebuild_players_table(conn)
    count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    assert count == 2
    row = conn.execute(
        "SELECT player_name, last_season FROM players WHERE player_id = 'luck'"
    ).fetchone()
    assert row == ("Andrew Luck", 2018)
    conn.close()
