"""HTTP client for FantasyPros Public API v2 (JSON)."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import requests

from src.rankings.fantasypros_config import ENV_API_KEY, get_fantasypros_api_key

# Public (limited) API — see https://api.fantasypros.com/public/v2/docs
BASE_URL = "https://api.fantasypros.com/public/v2/json"
DOCS_URL = "https://api.fantasypros.com/public/v2/docs"
DEFAULT_TIMEOUT_SEC = 60
DEFAULT_RETRIES = 5
DEFAULT_BACKOFF_SEC = 1.5
_MAX_RETRY_WAIT_SEC = 120.0
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "fantasypros"
DEFAULT_PLAYERS_CACHE_HOURS = 168.0


class FantasyProsAPIError(RuntimeError):
    """API request failed."""


def sport_key(sport_id: str) -> str:
    return str(sport_id).strip().upper()


def players_path(sport_id: str) -> str:
    return f"{sport_key(sport_id)}/players"


def consensus_rankings_path(sport_id: str, season: int) -> str:
    return f"{sport_key(sport_id)}/{int(season)}/consensus-rankings"


def projections_path(sport_id: str, season: int) -> str:
    """Projections routes use lowercase sport segment per OpenAPI."""
    return f"{sport_id.strip().lower()}/{int(season)}/projections"


def news_path(sport_id: str) -> str:
    return f"{sport_key(sport_id)}/news"


def players_cache_path(sport_id: str) -> Path:
    return _CACHE_DIR / f"{sport_id.strip().lower()}_players.json"


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
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

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

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload, "players-api"


def _basic_auth_header(api_key: str) -> dict[str, str]:
    token = base64.b64encode(f"X-Api-Key:{api_key}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _retry_wait_seconds(status_code: int, attempt: int, response: requests.Response) -> float:
    """Backoff for transient errors; honor Retry-After on 429 when present."""
    if status_code == 429:
        raw = (response.headers.get("Retry-After") or "").strip()
        if raw.isdigit():
            return min(max(float(raw), 2.0), _MAX_RETRY_WAIT_SEC)
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
) -> dict[str, Any]:
    """
    GET ``/public/v2/json/{path}`` and return parsed JSON object.

    ``path`` examples: ``NBA/players``, ``nba/2025/projections``.
    """
    key = api_key or get_fantasypros_api_key()
    url = f"{BASE_URL}/{path.lstrip('/')}"
    last_err: Exception | None = None
    last_status: int | None = None
    last_snippet = ""

    for headers in _auth_header_variants(key):
        for attempt in range(1, DEFAULT_RETRIES + 1):
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    params=params or {},
                    timeout=timeout_sec,
                )
            except requests.RequestException as exc:
                last_err = exc
                if attempt >= DEFAULT_RETRIES:
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

            if resp.status_code in (429, 500, 502, 503, 504) and attempt < DEFAULT_RETRIES:
                time.sleep(
                    _retry_wait_seconds(resp.status_code, attempt, resp)
                )
                continue
            break

        if last_status not in (401, 403):
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
        hint = " Rate limit hit — wait a minute and retry, or use a larger --delay on ingest."
    if last_status is not None:
        raise FantasyProsAPIError(
            f"FantasyPros API {last_status} for {url}: {snippet}.{hint}"
        )

    raise FantasyProsAPIError(f"FantasyPros API request failed for {url}: {last_err}")
