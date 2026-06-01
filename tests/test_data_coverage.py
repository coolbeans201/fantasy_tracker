import duckdb

from src.sports.data_coverage import sport_data_coverage


def test_sport_data_coverage_empty():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE mlb_player_season_stats (
            player_id VARCHAR, season INTEGER, position VARCHAR,
            team VARCHAR, games INTEGER, plate_appearances DOUBLE,
            fantasy_points_espn DOUBLE
        )
        """
    )
    conn.execute(
        """
        INSERT INTO mlb_player_season_stats VALUES
        ('p1', 2024, 'OF', 'NYY', 140, 600, 300.0)
        """
    )
    cov = sport_data_coverage(conn, "mlb")
    assert cov["stats_seasons"] == [2024]
    assert cov["gamelog_seasons"] == []
    assert cov["latest_stats_season"] == 2024
    conn.close()


def test_pre_2012_stats_not_listed_as_missing_draft_ecr():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE nba_player_season_stats (
            player_id VARCHAR, player_name VARCHAR, position VARCHAR,
            team VARCHAR, season INTEGER, games INTEGER,
            fantasy_points_espn DOUBLE
        )
        """
    )
    conn.execute(
        """
        INSERT INTO nba_player_season_stats VALUES
            ('old', 'Old Player', 'G', 'BOS', 2010, 82, 100.0),
            ('new', 'New Player', 'G', 'BOS', 2024, 82, 200.0)
        """
    )
    cov = sport_data_coverage(conn, "nba")
    assert 2010 in cov["draft_ecr_unsupported_seasons"]
    assert 2010 not in cov["stats_without_draft_ecr"]
    assert 2024 in cov["stats_without_draft_ecr"]
    conn.close()
