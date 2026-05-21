"""Load application settings from config."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

SETTINGS_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"


@lru_cache
def load_settings() -> dict:
    with SETTINGS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_min_games_default() -> int:
    settings = load_settings()
    thresholds_fallback = 8
    return int(settings.get("min_games_default", thresholds_fallback))
