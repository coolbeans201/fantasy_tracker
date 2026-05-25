"""Per-sport plugins and registry."""

from src.sports.registry import (
    SPORT_IDS,
    SportMeta,
    get_sport,
    list_sports,
    list_sports_with_data,
)

__all__ = [
    "SPORT_IDS",
    "SportMeta",
    "get_sport",
    "list_sports",
    "list_sports_with_data",
]
