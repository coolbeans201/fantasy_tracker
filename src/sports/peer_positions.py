"""Position keys for peer Z cohorts (exact position within sport)."""

from __future__ import annotations


def positions_for_peer_grouping(sport_id: str, position: str | None) -> str | None:
    """Normalize stored position to the peer cohort key (PG vs PG, not all guards)."""
    if position is None:
        return None
    sid = str(sport_id).strip().lower()
    if sid == "nba":
        from src.sports.nba.positions import normalize_nba_position

        return normalize_nba_position(position)
    if sid == "mlb":
        from src.sports.mlb.positions import normalize_mlb_position

        p = normalize_mlb_position(position)
        if p == "H":
            return "H"
        if p == "P":
            return None
        return p
    if sid == "nhl":
        from src.sports.nhl.positions import (
            GOALIE_POSITION,
            is_goalie_position,
            normalize_nhl_skater_position,
        )

        if is_goalie_position(position):
            return GOALIE_POSITION
        return normalize_nhl_skater_position(position) or "F"
    if sid == "nfl":
        from src.positions import positions_for_peer_grouping as nfl_group

        return nfl_group(position)
    return str(position).strip().upper() or None
