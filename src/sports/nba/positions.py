"""NBA fantasy positions."""

from __future__ import annotations

FANTASY_POSITIONS = ["PG", "SG", "SF", "PF", "C", "G", "F"]
LEADER_POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def leader_position_options() -> list[str]:
    return list(LEADER_POSITIONS)


def normalize_nba_position(pos: str | None) -> str | None:
    """Map NBA.com / PlayerIndex labels to fantasy buckets (PG–C)."""
    if not pos:
        return None
    p = str(pos).strip().upper().replace(" ", "")
    if p in LEADER_POSITIONS:
        return p
    if p in ("C", "CENTER"):
        return "C"
    if p in ("G", "GUARD"):
        return "SG"
    if p in ("F", "FORWARD"):
        return "SF"
    if "POINT" in p:
        return "PG"
    if "SHOOTING" in p:
        return "SG"
    if "SMALL" in p:
        return "SF"
    if "POWER" in p:
        return "PF"
    if "CENTER" in p:
        return "C"
    if "-" in p:
        parts = [x for x in p.split("-") if x]
        if "C" in parts and "F" not in parts and "G" not in parts:
            return "C"
        if "G" in parts and "F" in parts:
            return "SG"
        if "G" in parts:
            return "SG"
        if "F" in parts:
            return "SF"
    if p in ("G", "GF"):
        return "SG"
    if p in ("F",):
        return "SF"
    return None


def coerce_leader_selection(selected: list[str] | None, previous: list[str] | None = None) -> list[str]:
    del previous
    sel = [p for p in (selected or []) if p in LEADER_POSITIONS]
    return sel or list(LEADER_POSITIONS)
