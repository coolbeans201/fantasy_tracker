"""FantasyPros API key from environment (never commit secrets)."""

from __future__ import annotations

import os
from pathlib import Path

ENV_API_KEY = "FANTASYPROS_API_KEY"
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
