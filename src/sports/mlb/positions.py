"""MLB fantasy positions (hitters vs pitchers)."""

from __future__ import annotations

HITTER_POSITION = "H"
PITCHER_POSITION = "P"
LEADER_POSITIONS = [HITTER_POSITION, PITCHER_POSITION]


def leader_position_options() -> list[str]:
    return list(LEADER_POSITIONS)


def normalize_mlb_position(role: str | None) -> str | None:
    if role is None:
        return None
    r = str(role).strip().upper()
    if r in ("P", "SP", "RP", "PITCHER"):
        return PITCHER_POSITION
    if r in ("H", "B", "BAT", "HITTER", "OF", "IF", "C", "1B", "2B", "3B", "SS", "DH"):
        return HITTER_POSITION
    return None


def is_pitcher_only_selection(positions: list[str] | None) -> bool:
    return positions == [PITCHER_POSITION]


def is_hitter_only_selection(positions: list[str] | None) -> bool:
    return positions == [HITTER_POSITION]


def coerce_leader_selection(selected: list[str] | None, previous: list[str] | None = None) -> list[str]:
    sel = list(selected or [])
    if not sel:
        return [HITTER_POSITION]
    if PITCHER_POSITION in sel and HITTER_POSITION not in sel:
        return [PITCHER_POSITION]
    if HITTER_POSITION in sel and PITCHER_POSITION not in sel:
        return [HITTER_POSITION]
    return [HITTER_POSITION]
