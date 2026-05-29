"""NBA fantasy positions."""

from __future__ import annotations

FANTASY_POSITIONS = ["PG", "SG", "SF", "PF", "C", "G", "F"]
LEADER_POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def leader_position_options() -> list[str]:
    return list(LEADER_POSITIONS)


def default_leader_selection() -> list[str]:
    """Season Leaders multiselect default: all fantasy positions."""
    return list(LEADER_POSITIONS)


def normalize_nba_ecr_position(
    position: str | None,
    *,
    position_bucket: str | None = None,
) -> str | None:
    """
    Position on draft ECR rows (must match season-stats PG–C buckets).

    When FantasyPros is queried with ``position=PG``, the bucket label wins.
    """
    bucket = normalize_nba_position(position_bucket)
    if bucket in LEADER_POSITIONS:
        return bucket
    return normalize_nba_position(position)


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
    if p == "F":
        return "PF"
    if p == "FC":
        return "PF"
    if p == "FORWARD":
        return "SF"
    if "-" in p:
        parts = [x for x in p.split("-") if x]
        if parts in (["G", "F"], ["F", "G"]):
            return "SG"
        if parts in (["F", "C"], ["C", "F"]):
            return "PF"
        if parts and parts[0] in LEADER_POSITIONS:
            return parts[0]
        if "PG" in parts:
            return "PG"
        return None
    # Coarse guard labels stay unresolved (roster ingest may skip these).
    if p in ("G", "GUARD", "GF", "FORWARD"):
        return None
    return None


def coerce_leader_selection(selected: list[str] | None, previous: list[str] | None = None) -> list[str]:
    prev = list(previous or [])
    sel = [p for p in (selected or []) if p in LEADER_POSITIONS]
    if not sel:
        return default_leader_selection() if not prev else []
    return sel
