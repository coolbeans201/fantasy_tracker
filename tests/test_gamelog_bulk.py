"""Tests for parallel game-log ingest helpers."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.db.sport_schema import MLB_PLAYER_GAME_COLUMNS
from src.sports.gamelog_bulk import (
    align_gamelog_columns,
    bulk_replace_season_gamelogs,
    fetch_players_parallel,
    load_gamelog_cache,
    save_gamelog_cache,
)


def _frame(pid: str, gid: str, season: int = 2024) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "player_id": pid,
                "player_name": "Test",
                "season": season,
                "game_id": gid,
                "game_date": "2024-06-01",
                "game_index": 1,
                "team": "TST",
                "opponent": "OPP",
                "fantasy_points_espn": 10.0,
            }
        ]
    )


def test_align_gamelog_columns_legacy_cache():
    legacy = pd.DataFrame(
        [
            {
                "player_id": "1",
                "player_name": "A",
                "season": 2009,
                "game_id": "99",
                "game_date": "2009-04-01",
                "game_index": 1,
                "team": "NYY",
                "opponent": "BOS",
                "fantasy_points_espn": 5.0,
            }
        ]
    )
    out = align_gamelog_columns(legacy, MLB_PLAYER_GAME_COLUMNS)
    assert list(out.columns) == list(MLB_PLAYER_GAME_COLUMNS)
    assert out.iloc[0]["log_type"] == "hitting"
    assert out.iloc[0]["runs"] is None or pd.isna(out.iloc[0]["runs"])


def test_fetch_players_parallel_dedupes_and_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.sports.gamelog_bulk._CACHE_ROOT",
        tmp_path,
    )
    tasks = [{"player_id": "1"}, {"player_id": "2"}]

    def fetch_one(task):
        return _frame(str(task["player_id"]), "g1")

    frames, loaded, failed = fetch_players_parallel(
        tasks,
        fetch_one,
        sport_id="mlb",
        season=2024,
        workers=2,
        use_cache=False,
        progress_every=0,
    )
    assert loaded == 2
    assert failed == 0
    assert len(frames) == 2


def test_gamelog_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("src.sports.gamelog_bulk._CACHE_ROOT", tmp_path)
    frame = _frame("99", "g9")
    save_gamelog_cache("nhl", 2025, "99", frame)
    loaded = load_gamelog_cache("nhl", 2025, "99")
    assert loaded is not None
    assert len(loaded) == 1


def test_bulk_replace_season_gamelogs():
    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _test_game_stats (
            player_id VARCHAR,
            player_name VARCHAR,
            season INTEGER,
            game_id VARCHAR,
            game_date DATE,
            game_index INTEGER,
            team VARCHAR,
            opponent VARCHAR,
            fantasy_points_espn DOUBLE,
            PRIMARY KEY (player_id, season, game_id)
        )
        """
    )
    conn.execute(
        "INSERT INTO _test_game_stats VALUES ('old', 'Old', 2024, 'x', NULL, 0, '', '', 0)"
    )
    n = bulk_replace_season_gamelogs(
        conn,
        "_test_game_stats",
        2024,
        [_frame("a", "1"), _frame("b", "2")],
    )
    assert n == 2
    cnt = conn.execute(
        "SELECT COUNT(*) FROM _test_game_stats WHERE season = 2024"
    ).fetchone()[0]
    assert cnt == 2
    old = conn.execute(
        "SELECT COUNT(*) FROM _test_game_stats WHERE player_id = 'old'"
    ).fetchone()[0]
    assert old == 0
    conn.close()
