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


def get_min_games_default(sport_id: str | None = None) -> int:
    settings = load_settings()
    thresholds_fallback = 8
    global_default = int(settings.get("min_games_default", thresholds_fallback))
    if sport_id is None:
        return global_default
    by_sport = settings.get("min_games_default_by_sport") or {}
    return int(by_sport.get(str(sport_id).strip().lower(), global_default))
