"""MLB field and pitcher positions for leaders, ingest, and filters."""

from __future__ import annotations

# Legacy coarse cohorts (pre–detailed-position ingests)
LEGACY_HITTER = "H"
LEGACY_PITCHER = "P"

FIELD_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "OF", "DH", "UTIL"]
PITCHER_POSITIONS = ["SP", "RP"]
LEADER_POSITIONS = FIELD_POSITIONS + PITCHER_POSITIONS

# Backward-compatible aliases
HITTER_POSITION = LEGACY_HITTER
PITCHER_POSITION = LEGACY_PITCHER


def leader_position_options() -> list[str]:
    return list(LEADER_POSITIONS)


def is_pitcher_position(pos: str | None) -> bool:
    p = str(pos or "").strip().upper()
    return p in PITCHER_POSITIONS or p == LEGACY_PITCHER


def normalize_mlb_field_position(pos: str | None) -> str | None:
    """Map BRef / FanGraphs labels to a single fantasy field position."""
    if pos is None or (isinstance(pos, float) and str(pos) == "nan"):
        return None
    raw = str(pos).strip().upper()
    if not raw or raw in ("-", "NA", "NONE"):
        return None
    token = raw.replace(" ", "")
    for sep in ("/", "-", ","):
        if sep in token:
            token = token.split(sep)[0]
    aliases = {
        "P": None,
        "PITCHER": None,
        "SP": None,
        "RP": None,
        "IF": "UTIL",
        "OF": "OF",
        "OUTFIELD": "OF",
        "INFIELD": "UTIL",
        "CATCHER": "C",
        "FIRSTBASE": "1B",
        "SECONDBASE": "2B",
        "THIRDBASE": "3B",
        "SHORTSTOP": "SS",
        "LEFTFIELD": "LF",
        "CENTERFIELD": "CF",
        "RIGHTFIELD": "RF",
        "DESIGNATEDHITTER": "DH",
    }
    if token in aliases:
        return aliases[token]
    if token in FIELD_POSITIONS:
        return token
    return None


def classify_pitcher_role(
    games: float | int | None,
    games_started: float | int | None,
    saves: float | int | None,
) -> str:
    """SP vs RP from games started and saves (BRef / FanGraphs pitching lines)."""
    g = float(games or 0)
    gs = float(games_started or 0)
    sv = float(saves or 0)
    if g <= 0:
        return "RP"
    if gs >= 5 or (gs / g) >= 0.5:
        return "SP"
    if sv >= 1:
        return "RP"
    if gs > 0:
        return "SP"
    return "RP"


def normalize_mlb_position(role: str | None) -> str | None:
    """Accept legacy H/P or detailed positions."""
    if role is None:
        return None
    r = str(role).strip().upper()
    if r in LEADER_POSITIONS:
        return r
    if r in (LEGACY_PITCHER, "PITCHER"):
        return LEGACY_PITCHER
    if r in (LEGACY_HITTER, "B", "BAT", "HITTER"):
        return LEGACY_HITTER
    field = normalize_mlb_field_position(r)
    if field:
        return field
    if r in ("P", "SP", "RP"):
        return r if r in PITCHER_POSITIONS else LEGACY_PITCHER
    return None


def expand_leader_positions(selected: list[str] | None) -> list[str] | None:
    """Expand legacy H/P filters; None means no position filter (all)."""
    if not selected:
        return None
    expanded: list[str] = []
    for pos in selected:
        p = str(pos).strip().upper()
        if p == LEGACY_HITTER:
            expanded.extend(FIELD_POSITIONS)
        elif p == LEGACY_PITCHER:
            expanded.extend(PITCHER_POSITIONS)
        elif p in LEADER_POSITIONS:
            expanded.append(p)
    if not expanded:
        return None
    return list(dict.fromkeys(expanded))


def is_pitcher_only_selection(positions: list[str] | None) -> bool:
    expanded = expand_leader_positions(positions) or []
    return bool(expanded) and all(p in PITCHER_POSITIONS for p in expanded)


def is_hitter_only_selection(positions: list[str] | None) -> bool:
    expanded = expand_leader_positions(positions) or []
    return bool(expanded) and all(p in FIELD_POSITIONS for p in expanded)


def coerce_leader_selection(selected: list[str] | None, previous: list[str] | None = None) -> list[str]:
    del previous
    sel = [p for p in (selected or []) if p in LEADER_POSITIONS or p in (LEGACY_HITTER, LEGACY_PITCHER)]
    if not sel:
        return list(FIELD_POSITIONS)
    if LEGACY_PITCHER in sel and LEGACY_HITTER not in sel and not any(p in FIELD_POSITIONS for p in sel):
        return list(PITCHER_POSITIONS)
    if LEGACY_HITTER in sel and LEGACY_PITCHER not in sel and not any(p in PITCHER_POSITIONS for p in sel):
        return list(FIELD_POSITIONS)
    field = [p for p in sel if p in FIELD_POSITIONS]
    if field and not any(p in PITCHER_POSITIONS for p in sel):
        return field
    return sel
