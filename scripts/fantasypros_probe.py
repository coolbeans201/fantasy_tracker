#!/usr/bin/env python3
"""Test which FantasyPros Public API endpoints your key can access."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rankings.fantasypros_client import (  # noqa: E402
    BASE_URL,
    DOCS_URL,
    FantasyProsAPIError,
    _auth_header_variants,
    consensus_rankings_path,
    get_json,
    news_path,
    players_path,
    projections_path,
)
from src.rankings.fantasypros_config import ENV_API_KEY, get_fantasypros_api_key  # noqa: E402

_PROBE_PATH = news_path("NFL")
_PROBE_PARAMS = {"limit": 1}

_ENDPOINTS: list[tuple[str, str, dict | None]] = [
    ("NFL news", news_path("NFL"), {"limit": 1}),
    ("NFL players", players_path("NFL"), None),
    ("NBA players", players_path("NBA"), None),
    ("MLB players", players_path("MLB"), None),
    (
        "NBA consensus 2025",
        consensus_rankings_path("nba", 2025),
        {"position": "ALL", "type": "draft"},
    ),
    (
        "NBA projections 2025",
        projections_path("nba", 2025),
        {"position": "ALL", "type": "preseason"},
    ),
]


def _try_raw(key: str, path: str, headers: dict[str, str], params: dict | None) -> tuple[int, str]:
    url = f"{BASE_URL}/{path}"
    resp = requests.get(url, headers=headers, params=params or {}, timeout=30)
    return resp.status_code, (resp.text or "")[:120]


def main() -> None:
    try:
        key = get_fantasypros_api_key()
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)

    masked = f"{key[:4]}...{key[-4:]}" if len(key) >= 10 else "(short key)"
    print(f"{ENV_API_KEY} loaded ({masked}, len={len(key)})")
    print(f"Public API base: {BASE_URL}")
    print(f"Docs: {DOCS_URL}")
    print()

    print(f"Auth check on {_PROBE_PATH}:")
    status_no_key, body_no_key = _try_raw(key, _PROBE_PATH, {}, _PROBE_PARAMS)
    print(f"  no auth:              HTTP {status_no_key}  {body_no_key}")
    for i, headers in enumerate(_auth_header_variants(key), start=1):
        label = "x-api-key" if "Authorization" not in headers else "x-api-key + basic"
        status, body = _try_raw(key, _PROBE_PATH, headers, _PROBE_PARAMS)
        print(f"  mode {i} ({label}): HTTP {status}  {body}")
    print()

    ok = 0
    for label, path, params in _ENDPOINTS:
        try:
            data = get_json(path, params=params, api_key=key)
            count = data.get("count")
            extra = f", count={count}" if count is not None else ""
            print(f"  OK   {label} ({path}{extra})")
            ok += 1
        except FantasyProsAPIError as exc:
            print(f"  FAIL {label}: {exc}")

    print()
    if ok == 0:
        print(
            "No endpoints worked. Verify the key is for the Public API (see docs URL above).\n"
            "If you previously used /v2/json without /public/, that path returns 403 for public keys."
        )
        sys.exit(2)
    print(f"{ok}/{len(_ENDPOINTS)} endpoint groups succeeded.")
    print("\nNext:")
    print("  .\\.venv\\Scripts\\python.exe scripts\\refresh_fp_positions.py --sport nba")
    print("  .\\.venv\\Scripts\\python.exe scripts\\ingest_sport_rankings.py --sport nba --season 2025")


if __name__ == "__main__":
    main()
