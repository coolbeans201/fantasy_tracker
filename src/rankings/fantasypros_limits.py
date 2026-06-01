"""FantasyPros Public API limits for MLB / NBA / NHL ingest."""

from __future__ import annotations

_FP_SPORT_IDS = frozenset({"mlb", "nba", "nhl"})

# FantasyPros accepts season>=2012 in URLs, but historical draft boards are not reliable.
FP_SPORT_DRAFT_ECR_MIN_SEASON = 2012


def sport_draft_ecr_supported(sport_id: str, season: int) -> bool:
    """True when FantasyPros draft ECR ingest is expected to work for this sport/year."""
    sid = str(sport_id).strip().lower()
    if sid not in _FP_SPORT_IDS:
        return False
    try:
        year = int(season)
    except (TypeError, ValueError):
        return False
    return year >= FP_SPORT_DRAFT_ECR_MIN_SEASON
