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


MLB_REGULAR_SEASON_MAX_GAMES = 162


def mlb_regular_season_max_games(season: int) -> int:
    """Regular-season game cap for sanity checks (BRef G can include postseason)."""
    if int(season) == MLB_COVID_SHORTENED_SEASON:
        return 60
    return MLB_REGULAR_SEASON_MAX_GAMES
