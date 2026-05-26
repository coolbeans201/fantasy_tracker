"""NHL skater and goalie positions."""

from __future__ import annotations

# Legacy coarse cohorts (pre–detailed-position ingests)
LEGACY_SKATER = "S"
LEGACY_GOALIE = "G"

SKATER_POSITIONS = ["C", "LW", "RW", "D", "F"]
GOALIE_POSITION = "G"
LEADER_POSITIONS = SKATER_POSITIONS + [GOALIE_POSITION]

# Backward-compatible aliases
SKATER_POSITION = LEGACY_SKATER
GOALIE_POSITION = LEGACY_GOALIE


def leader_position_options() -> list[str]:
    return list(LEADER_POSITIONS)


def is_goalie_position(pos: str | None) -> bool:
    p = str(pos or "").strip().upper()
    return p in (GOALIE_POSITION, LEGACY_GOALIE, "GOALIE", "GOALTENDER")


def normalize_nhl_skater_position(code: str | None) -> str | None:
    """Map NHL.com positionCode (C, L, R, D, …) to C / LW / RW / D / F."""
    if code is None or (isinstance(code, float) and str(code) == "nan"):
        return None
    p = str(code).strip().upper().replace(" ", "")
    if p in SKATER_POSITIONS:
        return p
    if p in ("C", "CENTER"):
        return "C"
    if p in ("L", "LW", "LEFT", "LEFTWING", "LF"):
        return "LW"
    if p in ("R", "RW", "RIGHT", "RIGHTWING", "RF"):
        return "RW"
    if p in ("D", "LD", "RD", "DEF", "DEFENSE", "DEFENCE"):
        return "D"
    if p in ("F", "W", "FORWARD"):
        return "F"
    if is_goalie_position(p):
        return GOALIE_POSITION
    return None


def expand_leader_positions(selected: list[str] | None) -> list[str] | None:
    if not selected:
        return None
    expanded: list[str] = []
    for pos in selected:
        p = str(pos).strip().upper()
        if p == LEGACY_SKATER:
            expanded.extend(SKATER_POSITIONS)
        elif p in LEADER_POSITIONS:
            expanded.append(p)
    if not expanded:
        return None
    return list(dict.fromkeys(expanded))


def coerce_leader_selection(selected: list[str] | None, previous: list[str] | None = None) -> list[str]:
    del previous
    sel = [p for p in (selected or []) if p in LEADER_POSITIONS or p in (LEGACY_SKATER, LEGACY_GOALIE)]
    if not sel:
        return list(SKATER_POSITIONS)
    if LEGACY_GOALIE in sel or GOALIE_POSITION in sel:
        if not any(p in SKATER_POSITIONS or p == LEGACY_SKATER for p in sel):
            return [GOALIE_POSITION]
    skaters = [p for p in sel if p in SKATER_POSITIONS]
    if skaters and GOALIE_POSITION not in sel and LEGACY_GOALIE not in sel:
        return skaters
    return sel


def is_goalie_only_selection(positions: list[str] | None) -> bool:
    expanded = expand_leader_positions(positions) or []
    return bool(expanded) and all(is_goalie_position(p) for p in expanded)


def is_skater_only_selection(positions: list[str] | None) -> bool:
    expanded = expand_leader_positions(positions) or []
    return bool(expanded) and all(not is_goalie_position(p) for p in expanded)
