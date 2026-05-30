"""FantasyPros client pacing and consensus cache helpers."""

import time
from pathlib import Path

from src.rankings.fantasypros_client import (
    configure_fp_rate_limit,
    consensus_cache_path,
    read_json_cache,
    write_json_cache,
    _throttle_before_request,
)


def test_consensus_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.rankings.fantasypros_client._CACHE_DIR",
        tmp_path,
    )
    path = consensus_cache_path("nba", 2025, position="ALL", ranking_type="weekly", week=3)
    payload = {"week": 3, "players": []}
    write_json_cache(path, payload)
    assert read_json_cache(path) == payload


def test_throttle_enforces_min_interval(monkeypatch):
    configure_fp_rate_limit(min_interval_sec=0.2)
    t0 = time.monotonic()
    _throttle_before_request()
    _throttle_before_request()
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.18
