"""Position-aware stat columns for sport UI tables."""

from __future__ import annotations

# Omit ``games`` — profile/leaders tables already include it as a meta column.
MLB_HITTER_STATS = [
    "runs",
    "home_runs",
    "rbi",
    "stolen_bases",
]
MLB_PITCHER_STATS = ["wins", "strikeouts_pitch", "saves", "innings_pitched", "era"]

NBA_STATS = ["points", "rebounds", "assists", "steals", "blocks", "turnovers", "three_pointers"]

NHL_SKATER_STATS = ["goals", "assists", "points", "shots", "hits", "blocks", "plus_minus"]
NHL_GOALIE_STATS = ["wins", "saves", "goals_against", "shutouts"]


def display_stats_for_leader_selection(sport_id: str, positions: list[str] | None) -> list[str]:
    """Stat columns for a leaders table from the position multiselect."""
    sid = str(sport_id).strip().lower()
    if sid == "mlb":
        from src.sports.mlb.positions import is_hitter_only_selection, is_pitcher_only_selection

        if is_pitcher_only_selection(positions):
            return display_stats_for_sport("mlb", "SP")
        return display_stats_for_sport("mlb", "OF")
    if sid == "nhl":
        from src.sports.nhl.positions import is_goalie_only_selection

        if is_goalie_only_selection(positions):
            return display_stats_for_sport("nhl", "G")
        return display_stats_for_sport("nhl", "C")
    if sid == "nba":
        return display_stats_for_sport("nba", None)
    return []


def display_stats_for_sport(sport_id: str, position: str | None) -> list[str]:
    sid = str(sport_id).strip().lower()
    pos = str(position or "").strip().upper()
    if sid == "mlb":
        from src.sports.mlb.positions import is_pitcher_position

        if is_pitcher_position(pos):
            return list(MLB_PITCHER_STATS)
        return list(MLB_HITTER_STATS)
    if sid == "nba":
        return list(NBA_STATS)
    if sid == "nhl":
        from src.sports.nhl.positions import is_goalie_position

        if is_goalie_position(pos):
            return list(NHL_GOALIE_STATS)
        return list(NHL_SKATER_STATS)
    return []
