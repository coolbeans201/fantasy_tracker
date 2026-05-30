"""FantasyPros API key from environment (never commit secrets)."""

from __future__ import annotations

import os
from pathlib import Path

ENV_API_KEY = "FANTASYPROS_API_KEY"
ENV_MIN_INTERVAL = "FANTASYPROS_MIN_INTERVAL_SEC"
ENV_429_BASE_WAIT = "FANTASYPROS_429_BASE_WAIT_SEC"

# Public API tier (contact api@fantasypros.com to confirm for your key).
FP_PUBLIC_API_DAILY_CALL_LIMIT = 100
_DOTENV_LOADED = False


def _load_dotenv_if_present() -> None:
    """Load project ``.env`` into os.environ when keys are not already set."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ[key] = value


def get_fantasypros_api_key() -> str:
    """
    Return API key from ``FANTASYPROS_API_KEY``.

    Also reads ``.env`` in the project root if the variable is not already set
    in the process environment.

    Raises:
        RuntimeError: if the variable is unset or empty.
    """
    _load_dotenv_if_present()
    key = os.environ.get(ENV_API_KEY, "").strip()
    if not key:
        raise RuntimeError(
            f"Set {ENV_API_KEY} in your environment or in a local .env file "
            f"(see .env.example). Do not commit keys to the repository."
        )
    return key


def fp_min_interval_sec() -> float:
    """Minimum seconds between FantasyPros HTTP requests (global throttle)."""
    _load_dotenv_if_present()
    raw = os.environ.get(ENV_MIN_INTERVAL, "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return 5.0


def fp_429_base_wait_sec() -> float:
    """Base cooldown after HTTP 429 when Retry-After header is absent."""
    _load_dotenv_if_present()
    raw = os.environ.get(ENV_429_BASE_WAIT, "").strip()
    if raw:
        try:
            return max(10.0, float(raw))
        except ValueError:
            pass
    return 90.0
