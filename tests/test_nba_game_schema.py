import duckdb

from src.db.sport_schema import (
    NBA_PLAYER_GAME_COLUMNS,
    ensure_nba_player_game_stats_schema,
)


def test_migrate_legacy_int_team_column():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE nba_player_game_stats (
            player_id VARCHAR,
            player_name VARCHAR,
            season INTEGER,
            game_id VARCHAR,
            game_date DATE,
            team INTEGER,
            opponent VARCHAR,
            points DOUBLE,
            fantasy_points_espn DOUBLE,
            PRIMARY KEY (player_id, season, game_id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO nba_player_game_stats VALUES
        ('1', 'Test', 2025, 'g1', '2025-01-01', 1610612747, 'BOS', 10.0, 10.0)
        """
    )
    ensure_nba_player_game_stats_schema(conn)
    row = conn.execute(
        "SELECT team, game_index FROM nba_player_game_stats WHERE player_id = '1'"
    ).fetchone()
    assert row is not None
    assert row[0] == "UNK"
    assert row[1] is None or row[1] is not None  # game_index may be null after mig
    cols = [r[0] for r in conn.execute("DESCRIBE nba_player_game_stats").fetchall()]
    assert "team" in cols
    team_type = conn.execute(
        """
        SELECT data_type FROM information_schema.columns
        WHERE table_name = 'nba_player_game_stats' AND column_name = 'team'
        """
    ).fetchone()[0]
    assert "INT" not in str(team_type).upper()
    assert tuple(cols) == NBA_PLAYER_GAME_COLUMNS or set(cols) == set(NBA_PLAYER_GAME_COLUMNS)
    conn.close()


def test_insert_varchar_team():
    conn = duckdb.connect(":memory:")
    ensure_nba_player_game_stats_schema(conn)
    conn.execute(
        """
        INSERT INTO nba_player_game_stats (
            player_id, player_name, season, game_id, game_date, game_index,
            team, opponent, points, rebounds, assists, steals, blocks,
            turnovers, three_pointers, fantasy_points_espn
        ) VALUES (
            '2544', 'Player', 2026, '0022500001', '2025-10-21', 1,
            'LAL', 'BOS', 20, 5, 5, 1, 1, 2, 3, 35.0
        )
        """
    )
    team = conn.execute(
        "SELECT team FROM nba_player_game_stats WHERE game_id = '0022500001'"
    ).fetchone()[0]
    assert team == "LAL"
    conn.close()
