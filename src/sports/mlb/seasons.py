"""MLB season calendar exceptions."""

from __future__ import annotations

# 60-game regular season; career Z vs full-season baselines is misleading.
MLB_COVID_SHORTENED_SEASON = 2020


def mlb_career_z_excluded_season(season: object) -> bool:
    """True when career Z should not be computed or shown for this MLB season."""
    try:
        return int(season) == MLB_COVID_SHORTENED_SEASON
    except (TypeError, ValueError):
        return False
