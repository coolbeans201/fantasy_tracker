"""HTTP client for FantasyPros Public API v2 (JSON)."""

from __future__ import annotations

import base64
import json
import random
import threading
import time
from pathlib import Path
from typing import Any

import requests

from src.rankings.fantasypros_config import (
    ENV_API_KEY,
    fp_429_base_wait_sec,
    fp_min_interval_sec,
    get_fantasypros_api_key,
)

# Public (limited) API — see https://api.fantasypros.com/public/v2/docs
BASE_URL = "https://api.fantasypros.com/public/v2/json"
DOCS_URL = "https://api.fantasypros.com/public/v2/docs"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_RETRIES = 4
DEFAULT_BACKOFF_SEC = 1.5
_MAX_RETRY_WAIT_SEC = 180.0
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "fantasypros"
DEFAULT_PLAYERS_CACHE_HOURS = 168.0

_rate_lock = threading.Lock()
_last_request_at: float = 0.0
_min_interval_sec: float | None = None
_429_base_wait_sec: float | None = None


class FantasyProsAPIError(RuntimeError):
    """API request failed."""


def configure_fp_rate_limit(
    *,
    min_interval_sec: float | None = None,
    base_429_wait_sec: float | None = None,
) -> None:
    """
    Tune global pacing for this process (e.g. before weekly backfill).

    ``min_interval_sec``: minimum gap between any two FP HTTP requests.
    ``base_429_wait_sec``: sleep after 429 when Retry-After is missing.
    """
    global _min_interval_sec, _429_base_wait_sec
    if min_interval_sec is not None:
        _min_interval_sec = max(0.0, float(min_interval_sec))
    if base_429_wait_sec is not None:
        _429_base_wait_sec = max(10.0, float(base_429_wait_sec))


def _effective_min_interval() -> float:
    if _min_interval_sec is not None:
        return _min_interval_sec
    return fp_min_interval_sec()


def _effective_429_base_wait() -> float:
    if _429_base_wait_sec is not None:
        return _429_base_wait_sec
    return fp_429_base_wait_sec()


def _throttle_before_request() -> None:
    """Enforce a global minimum gap between FP API calls."""
    global _last_request_at
    interval = _effective_min_interval()
    if interval <= 0:
        return
    with _rate_lock:
        now = time.monotonic()
        wait = interval - (now - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def sport_key(sport_id: str) -> str:
    return str(sport_id).strip().upper()


def players_path(sport_id: str) -> str:
    return f"{sport_key(sport_id)}/players"


def consensus_rankings_path(sport_id: str, season: int) -> str:
    return f"{sport_key(sport_id)}/{int(season)}/consensus-rankings"


def rankings_path(sport_id: str, season: int) -> str:
    """Aggregate rankings (ECR nested under each player's ``rank`` object)."""
    return f"{sport_key(sport_id)}/{int(season)}/rankings"


def projections_path(sport_id: str, season: int) -> str:
    """Projections routes use lowercase sport segment per OpenAPI."""
    return f"{sport_id.strip().lower()}/{int(season)}/projections"


def news_path(sport_id: str) -> str:
    return f"{sport_key(sport_id)}/news"


def players_cache_path(sport_id: str) -> Path:
    return _CACHE_DIR / f"{sport_id.strip().lower()}_players.json"


def consensus_cache_path(
    sport_id: str,
    season: int,
    *,
    position: str,
    ranking_type: str,
    week: int | None = None,
) -> Path:
    sid = sport_id.strip().lower()
    pos = str(position).strip().upper()
    rtype = str(ranking_type).strip().lower()
    week_part = f"_w{int(week)}" if week is not None else ""
    return _CACHE_DIR / f"{sid}_{int(season)}_{rtype}_{pos}{week_part}.json"


def rankings_cache_path(sport_id: str, season: int, *, week: int) -> Path:
    sid = sport_id.strip().lower()
    return _CACHE_DIR / f"{sid}_{int(season)}_rankings_w{int(week)}.json"


def read_json_cache(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def write_json_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def load_players_payload(
    sport_id: str,
    *,
    refresh: bool = False,
    cache_hours: float = DEFAULT_PLAYERS_CACHE_HOURS,
    allow_stale_on_rate_limit: bool = True,
) -> tuple[dict[str, Any], str]:
    """
    Load ``/{SPORT}/players`` from disk cache when possible.

    Returns ``(payload, source)`` where source is ``players-cache``,
    ``players-cache-stale``, or ``players-api``.
    """
    path = players_cache_path(sport_id)

    def _read_cache() -> dict[str, Any] | None:
        return read_json_cache(path)

    if not refresh:
        cached = _read_cache()
        if cached is not None:
            age_h = (time.time() - path.stat().st_mtime) / 3600.0
            if age_h < cache_hours:
                return cached, "players-cache"

    try:
        payload = get_json(players_path(sport_id))
    except FantasyProsAPIError as exc:
        if allow_stale_on_rate_limit and "429" in str(exc):
            stale = _read_cache()
            if stale is not None:
                return stale, "players-cache-stale"
        raise

    write_json_cache(path, payload)
    return payload, "players-api"


def _basic_auth_header(api_key: str) -> dict[str, str]:
    token = base64.b64encode(f"X-Api-Key:{api_key}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _retry_wait_seconds(status_code: int, attempt: int, response: requests.Response) -> float:
    """Backoff for transient errors; honor Retry-After on 429 when present."""
    if status_code == 429:
        raw = (response.headers.get("Retry-After") or "").strip()
        if raw.isdigit():
            base = float(raw)
        else:
            base = _effective_429_base_wait()
        # Exponential stretch on repeated 429s in one request.
        scaled = base * (1.25 ** max(attempt - 1, 0))
        jitter = random.uniform(0.0, min(5.0, scaled * 0.1))
        return min(max(scaled + jitter, 10.0), _MAX_RETRY_WAIT_SEC)
    return min(DEFAULT_BACKOFF_SEC * (2 ** max(attempt - 1, 0)), _MAX_RETRY_WAIT_SEC)


def _auth_header_variants(api_key: str) -> list[dict[str, str]]:
    basic = _basic_auth_header(api_key)
    return [
        {"x-api-key": api_key},
        {"x-api-key": api_key, **basic},
    ]


def get_json(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    api_key: str | None = None,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    max_retries: int | None = None,
    try_auth_fallback: bool = True,
) -> dict[str, Any]:
    """
    GET ``/public/v2/json/{path}`` and return parsed JSON object.

    Uses a process-wide throttle and conservative 429 handling (no auth-mode
    doubling after rate limit).

    ``max_retries``: HTTP attempts per auth mode (ingest uses 2 so 429 fails fast).
    """
    key = api_key or get_fantasypros_api_key()
    url = f"{BASE_URL}/{path.lstrip('/')}"
    last_err: Exception | None = None
    last_status: int | None = None
    last_snippet = ""
    retries = max(1, int(max_retries if max_retries is not None else DEFAULT_RETRIES))
    header_modes = _auth_header_variants(key) if try_auth_fallback else [{"x-api-key": key}]

    for headers in header_modes:
        for attempt in range(1, retries + 1):
            _throttle_before_request()
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    params=params or {},
                    timeout=timeout_sec,
                )
            except requests.RequestException as exc:
                last_err = exc
                if attempt >= retries:
                    break
                time.sleep(DEFAULT_BACKOFF_SEC * attempt)
                continue

            if resp.status_code == 200:
                data = resp.json()
                if not isinstance(data, dict):
                    raise FantasyProsAPIError(f"Expected JSON object from {url}")
                return data

            last_status = resp.status_code
            last_snippet = (resp.text or "")[:300]

            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = _retry_wait_seconds(resp.status_code, attempt, resp)
                if resp.status_code == 429:
                    print(f"  HTTP 429 — waiting {wait:.0f}s (attempt {attempt}/{retries})")
                time.sleep(wait)
                continue
            break

        # Do not burn a second auth mode after rate limit — same key, more 429s.
        if last_status == 429:
            break
        if last_status not in (401, 403) or not try_auth_fallback:
            break

    snippet = last_snippet
    hint = ""
    if last_status == 401:
        hint = f" Check {ENV_API_KEY} matches your Public API key from FantasyPros."
    elif last_status == 403:
        hint = (
            f" Confirm you are using the Public API ({DOCS_URL}), not the legacy /v2/json path."
        )
    elif last_status == 429:
        hint = (
            " Rate limit — increase --delay / --fp-min-interval, wait 5–15 min, then re-run; "
            "cached weeks under data/cache/fantasypros/ are skipped on retry."
        )
    if last_status is not None:
        raise FantasyProsAPIError(
            f"FantasyPros API {last_status} for {url}: {snippet}.{hint}"
        )

    raise FantasyProsAPIError(f"FantasyPros API request failed for {url}: {last_err}")
