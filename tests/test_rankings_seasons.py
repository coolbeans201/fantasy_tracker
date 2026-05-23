"""Per-season rankings availability."""

import duckdb

from src.db.queries import list_rankings_seasons, season_has_rankings


def test_season_has_rankings_false_when_empty():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE ecr_draft (
            player_id VARCHAR, season INTEGER, position VARCHAR,
            ecr_rank INTEGER, ecr_sd DOUBLE, player_name VARCHAR,
            team VARCHAR, fantasypros_id VARCHAR, scrape_date DATE,
            PRIMARY KEY (player_id, season, position)
        )
        """
    )
    assert season_has_rankings(conn, 2023) is False
    assert list_rankings_seasons(conn) == []
    conn.close()


def test_season_has_rankings_true_for_present_season():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE ecr_draft (
            player_id VARCHAR, season INTEGER, position VARCHAR,
            ecr_rank INTEGER, ecr_sd DOUBLE, player_name VARCHAR,
            team VARCHAR, fantasypros_id VARCHAR, scrape_date DATE,
            PRIMARY KEY (player_id, season, position)
        )
        """
    )
    rows = ", ".join(
        f"('00-{i:03d}', 2020, 'QB', {i}, NULL, 'P{i}', 'KC', NULL, NULL)"
        for i in range(1, 51)
    )
    conn.execute(f"INSERT INTO ecr_draft VALUES {rows}")
    conn.execute(
        """
        INSERT INTO ecr_draft VALUES
        ('00-100', 2021, 'RB', 5, NULL, 'B', 'DAL', NULL, NULL)
        """
    )
    assert season_has_rankings(conn, 2020) is True
    assert season_has_rankings(conn, 2021) is False
    assert season_has_rankings(conn, 2019) is False
    assert list_rankings_seasons(conn) == [2020]
    conn.close()
