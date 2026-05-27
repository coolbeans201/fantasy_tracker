"""NBA fantasy positions."""

from __future__ import annotations

FANTASY_POSITIONS = ["PG", "SG", "SF", "PF", "C", "G", "F"]
LEADER_POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def leader_position_options() -> list[str]:
    return list(LEADER_POSITIONS)


def normalize_nba_position(pos: str | None) -> str | None:
    """Map NBA.com roster / PlayerIndex labels to fantasy buckets (PG–C)."""
    if not pos:
        return None
    p = str(pos).strip().upper().replace(" ", "")
    if p in LEADER_POSITIONS:
        return p
    if p in ("C", "CENTER"):
        return "C"
    if p in ("PG", "POINTGUARD", "POINT-GUARD"):
        return "PG"
    if p in ("SG", "SHOOTINGGUARD", "SHOOTING-GUARD"):
        return "SG"
    if p in ("SF", "SMALLFORWARD", "SMALL-FORWARD"):
        return "SF"
    if p in ("PF", "POWERFORWARD", "POWER-FORWARD"):
        return "PF"
    if "POINT" in p:
        return "PG"
    if "SHOOTING" in p:
        return "SG"
    if "SMALL" in p:
        return "SF"
    if "POWER" in p:
        return "PF"
    if "CENTER" in p and "FORWARD" not in p:
        return "C"
    if "-" in p:
        parts = [x for x in p.split("-") if x]
        if parts and parts[0] in LEADER_POSITIONS:
            return parts[0]
        if "PG" in parts:
            return "PG"
        # Ambiguous hybrids (G-F, F-C, etc.) are left unresolved by design.
        return None
    # Generic buckets are intentionally not coerced.
    if p in ("G", "GUARD", "GF", "F", "FORWARD", "FC"):
        return None
    return None


def coerce_leader_selection(selected: list[str] | None, previous: list[str] | None = None) -> list[str]:
    del previous
    sel = [p for p in (selected or []) if p in LEADER_POSITIONS]
    return sel or list(LEADER_POSITIONS)
