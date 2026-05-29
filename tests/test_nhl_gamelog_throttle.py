"""NHL game-log rate limit helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.sports.nhl.gamelogs import _retry_wait_seconds


def test_retry_wait_honors_retry_after_on_429():
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {"Retry-After": "5"}
    assert _retry_wait_seconds(1, resp) == 5.0


def test_retry_wait_exponential_without_header():
    resp = MagicMock()
    resp.status_code = 429
    resp.headers = {}
    wait = _retry_wait_seconds(3, resp)
    assert wait >= 4.0
