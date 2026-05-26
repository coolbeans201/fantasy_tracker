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
    """Skaters (S) and goalies (G) shortcuts plus detailed positions."""
    return [LEGACY_SKATER] + SKATER_POSITIONS + [GOALIE_POSITION]


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
        elif is_goalie_position(p):
            expanded.append(GOALIE_POSITION)
        elif p in SKATER_POSITIONS:
            expanded.append(p)
    if not expanded:
        return None
    return list(dict.fromkeys(expanded))


def _skater_subset(selected: list[str]) -> list[str]:
    if LEGACY_SKATER in selected:
        return list(SKATER_POSITIONS)
    skaters = [p for p in selected if p in SKATER_POSITIONS]
    return skaters or list(SKATER_POSITIONS)


def _goalie_subset(selected: list[str]) -> list[str]:
    if LEGACY_GOALIE in selected or GOALIE_POSITION in selected:
        return [GOALIE_POSITION]
    return [GOALIE_POSITION]


def _is_goalie_pick(pos: str) -> bool:
    return is_goalie_position(pos)


def _is_skater_pick(pos: str) -> bool:
    p = str(pos).strip().upper()
    return p in SKATER_POSITIONS or p == LEGACY_SKATER


def coerce_leader_selection(
    selected: list[str] | None,
    previous: list[str] | None = None,
) -> list[str]:
    """
    Season Leaders rules (mirrors NFL K/DST and MLB H/P):
    - Default → skaters only
    - Goalie (G) cannot mix with skater positions
    """
    sel = [
        p
        for p in (selected or [])
        if p in LEADER_POSITIONS or p in (LEGACY_SKATER, LEGACY_GOALIE)
    ]
    prev = list(previous or [])

    if not sel:
        return list(SKATER_POSITIONS)

    added = set(sel) - set(prev)
    removed = set(prev) - set(sel)

    if LEGACY_GOALIE in added or GOALIE_POSITION in added or any(_is_goalie_pick(p) for p in added):
        if not any(_is_skater_pick(p) for p in added):
            return _goalie_subset(sel)

    if LEGACY_SKATER in added or any(_is_skater_pick(p) for p in added):
        if not any(_is_goalie_pick(p) for p in added):
            return _skater_subset(sel)

    if is_goalie_only_selection(prev) and any(_is_skater_pick(p) for p in added):
        return _skater_subset(sel)
    if is_skater_only_selection(prev) and any(_is_goalie_pick(p) for p in added):
        return _goalie_subset(sel)

    if is_goalie_only_selection(sel):
        return _goalie_subset(sel)
    if is_skater_only_selection(sel):
        return _skater_subset(sel)

    if is_goalie_only_selection(prev):
        return _goalie_subset(prev)
    if is_skater_only_selection(prev):
        return _skater_subset(prev)

    return list(SKATER_POSITIONS)


def is_goalie_only_selection(positions: list[str] | None) -> bool:
    expanded = expand_leader_positions(positions) or []
    return bool(expanded) and all(is_goalie_position(p) for p in expanded)


def is_skater_only_selection(positions: list[str] | None) -> bool:
    expanded = expand_leader_positions(positions) or []
    return bool(expanded) and all(not is_goalie_position(p) for p in expanded)


COMPARE_GROUP_SKATER = "skater"
COMPARE_GROUP_GOALIE = "goalie"


def compare_cohort(position: str | None) -> str:
    if is_goalie_position(position):
        return COMPARE_GROUP_GOALIE
    return COMPARE_GROUP_SKATER


def compare_incompatible_message(cohort_a: str, cohort_b: str) -> str:
    labels = {
        COMPARE_GROUP_SKATER: "skaters",
        COMPARE_GROUP_GOALIE: "goalies",
    }
    a = labels.get(cohort_a, cohort_a)
    b = labels.get(cohort_b, cohort_b)
    return (
        f"These selections are not comparable: one side is **{a}** and the other is **{b}**. "
        "Compare skaters to skaters or goalies to goalies only."
    )
