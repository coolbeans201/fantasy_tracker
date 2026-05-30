"""Weekly rank surprise for MLB / NBA / NHL."""

import duckdb
import pandas as pd

from src.analytics.sport_weekly_surprise import compute_sport_weekly_surprise_for_season
from src.analytics.surprise import assign_positional_ecr_ranks
from src.rankings.rankings_store import insert_ecr_weekly


def _init_weekly_db(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE player_week_stats (
            sport VARCHAR NOT NULL,
            player_id VARCHAR NOT NULL,
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            position VARCHAR NOT NULL,
            fantasy_points DOUBLE,
            games INTEGER,
            week_start DATE,
            week_end DATE,
            PRIMARY KEY (sport, player_id, season, week, position)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE ecr_weekly (
            sport VARCHAR NOT NULL,
            player_id VARCHAR NOT NULL,
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            position VARCHAR NOT NULL,
            ecr_rank INTEGER NOT NULL,
            ecr_sd DOUBLE,
            player_name VARCHAR,
            team VARCHAR,
            fantasypros_id VARCHAR,
            scrape_date DATE,
            PRIMARY KEY (sport, player_id, season, week, position)
        )
        """
    )


def test_weekly_surprise_rank_delta_nba(monkeypatch):
    conn = duckdb.connect(":memory:")
    _init_weekly_db(conn)
    monkeypatch.setattr(
        "src.analytics.sport_weekly_surprise.season_has_weekly_rankings",
        lambda _c, _s, sport: sport == "nba",
    )
    monkeypatch.setattr(
        "src.analytics.sport_weekly_surprise._ensure_week_stats",
        lambda _c, _sid, _season: conn.execute(
            "SELECT * FROM player_week_stats"
        ).df(),
    )
    season = 2025

    weeks = pd.DataFrame(
        [
            {
                "sport": "nba",
                "player_id": "a",
                "season": season,
                "week": 1,
                "position": "PG",
                "fantasy_points": 50.0,
                "games": 3,
                "week_start": "2025-01-06",
                "week_end": "2025-01-12",
            },
            {
                "sport": "nba",
                "player_id": "b",
                "season": season,
                "week": 1,
                "position": "PG",
                "fantasy_points": 30.0,
                "games": 3,
                "week_start": "2025-01-06",
                "week_end": "2025-01-12",
            },
        ]
    )
    conn.register("_wks", weeks)
    conn.execute("INSERT INTO player_week_stats SELECT * FROM _wks")
    conn.unregister("_wks")

    ecr = pd.DataFrame(
        [
            {
                "sport": "nba",
                "player_id": "a",
                "season": season,
                "week": 1,
                "position": "PG",
                "ecr_rank": 5,
                "player_name": "A",
            },
            {
                "sport": "nba",
                "player_id": "b",
                "season": season,
                "week": 1,
                "position": "PG",
                "ecr_rank": 2,
                "player_name": "B",
            },
        ]
    )
    insert_ecr_weekly(conn, ecr)

    frame = compute_sport_weekly_surprise_for_season(
        conn, "nba", season, "espn_default", position="PG"
    )
    assert not frame.empty
    row_a = frame[frame["player_id"] == "a"].iloc[0]
    assert int(row_a["finish_rank"]) == 1
    assert int(row_a["weekly_ecr"]) == 5
    assert int(row_a["rank_delta"]) == 4


def test_assign_positional_ecr_on_weekly_frame():
    raw = pd.DataFrame(
        [
            {"player_id": "1", "position": "PG", "ecr_rank": 120, "week": 1},
            {"player_id": "2", "position": "PG", "ecr_rank": 8, "week": 1},
        ]
    )
    out = assign_positional_ecr_ranks(raw)
    assert int(out[out["player_id"] == "2"].iloc[0]["ecr_rank"]) == 1
