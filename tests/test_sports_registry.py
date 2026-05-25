"""Multi-sport registry and season listing."""

import duckdb

from src.db.connection import init_schema, list_sport_seasons
from src.sports.registry import SPORT_IDS, get_sport, list_sports, season_leaders


def test_all_sports_registered():
    assert len(list_sports()) == len(SPORT_IDS)
    for sid in SPORT_IDS:
        meta = get_sport(sid)
        assert meta.sport_id == sid
        assert meta.hub_page.startswith("pages/")


def test_list_sport_seasons_nfl_empty():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    assert list_sport_seasons(conn, "nfl") == []
    conn.execute(
        """
        INSERT INTO ingest_manifest (sport, season, ingested_at, row_count)
        VALUES ('nfl', 2023, now(), 100)
        """
    )
    assert list_sport_seasons(conn, "nfl") == [2023]


def test_mlb_season_leaders_empty():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    df = season_leaders(conn, "mlb", 2024, "espn")
    assert df.empty
