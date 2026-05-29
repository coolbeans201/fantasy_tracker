"""NBA player ID and position normalization."""

import json
from pathlib import Path

import pytest

from src.sports.nba import player_positions
from src.sports.nba.player_positions import fetch_season_positions, normalize_player_id
from src.sports.nba.positions import (
    LEADER_POSITIONS,
    coerce_leader_selection,
    default_leader_selection,
    normalize_nba_position,
)


def test_normalize_player_id_strips_float_suffix():
    assert normalize_player_id(2544.0) == "2544"
    assert normalize_player_id("2544.0") == "2544"
    assert normalize_player_id("1630162") == "1630162"


def test_default_leader_selection_all_positions():
    assert default_leader_selection() == LEADER_POSITIONS


def test_coerce_leader_selection_empty_returns_all():
    assert coerce_leader_selection([]) == LEADER_POSITIONS


def test_normalize_nba_roster_labels():
    assert normalize_nba_position("PG") == "PG"
    assert normalize_nba_position("G-F") == "SG"
    assert normalize_nba_position("F-C") == "PF"
    assert normalize_nba_position("F") == "PF"
    assert normalize_nba_position("FC") == "PF"
    assert normalize_nba_position("C") == "C"
    assert normalize_nba_position("Forward") == "SF"


def test_fetch_season_positions_cache_hit_skips_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cache = tmp_path / "positions_2025.json"
    cache.write_text(json.dumps({"123": "PG"}), encoding="utf-8")

    def fail(*_a, **_k):
        raise AssertionError("nba_api should not run on cache hit")

    monkeypatch.setattr(player_positions, "_positions_from_player_index", fail)
    monkeypatch.setattr(player_positions, "_positions_from_team_rosters", fail)

    out = fetch_season_positions(2025, cache_dir=tmp_path)
    assert out == {"123": "PG"}


def test_fetch_season_positions_empty_cache_file_refetches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "positions_2025.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(player_positions, "_positions_from_player_index", lambda _s: {"1": "C"})
    monkeypatch.setattr(player_positions, "_positions_from_team_rosters", lambda _s: {})

    out = fetch_season_positions(2025, cache_dir=tmp_path)
    assert out == {"1": "C"}
    data = json.loads((tmp_path / "positions_2025.json").read_text(encoding="utf-8"))
    assert data == {"1": "C"}


def test_fetch_season_positions_refresh_overwrites_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "positions_2025.json").write_text(json.dumps({"123": "PG"}), encoding="utf-8")

    monkeypatch.setattr(
        player_positions, "_positions_from_player_index", lambda _s: {"123": "SG"}
    )
    monkeypatch.setattr(player_positions, "_positions_from_team_rosters", lambda _s: {})

    out = fetch_season_positions(2025, refresh_positions=True, cache_dir=tmp_path)
    assert out == {"123": "SG"}


def test_positions_cache_separate_files_for_rosters_mode(tmp_path: Path):
    plain = tmp_path / "positions_2025.json"
    rosters = tmp_path / "positions_2025_rosters.json"
    plain.write_text(json.dumps({"1": "PG"}), encoding="utf-8")
    rosters.write_text(json.dumps({"1": "SG"}), encoding="utf-8")

    assert fetch_season_positions(2025, use_rosters=False, cache_dir=tmp_path) == {"1": "PG"}
    assert fetch_season_positions(2025, use_rosters=True, cache_dir=tmp_path) == {"1": "SG"}
