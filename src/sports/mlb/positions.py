"""MLB field and pitcher positions for leaders, ingest, and filters."""

from __future__ import annotations

# Legacy coarse cohorts (UI filters only — not stored on player rows)
LEGACY_HITTER = "H"
LEGACY_PITCHER = "P"

# Fallback when BRef Pos and MLB API primaryPosition are both missing — not a
# “DH eligibility” tag. Most rows get CF/1B/OF/etc.; only a small share is DH.
DEFAULT_HITTER_POSITION = "DH"

FIELD_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "OF", "DH", "UTIL"]
PITCHER_POSITIONS = ["SP", "RP"]
LEADER_POSITIONS = FIELD_POSITIONS + PITCHER_POSITIONS

# Backward-compatible aliases
HITTER_POSITION = LEGACY_HITTER
PITCHER_POSITION = LEGACY_PITCHER


def leader_position_options() -> list[str]:
    """Hitters (H) and pitchers (P) shortcuts plus detailed positions."""
    return [LEGACY_HITTER, LEGACY_PITCHER] + FIELD_POSITIONS + PITCHER_POSITIONS


def default_leader_selection() -> list[str]:
    """Season Leaders multiselect default: all field positions (hitters only)."""
    return list(FIELD_POSITIONS)


def is_pitcher_position(pos: str | None) -> bool:
    p = str(pos or "").strip().upper()
    return p in PITCHER_POSITIONS or p == LEGACY_PITCHER


def normalize_mlb_ecr_position(
    position: str | None,
    *,
    position_bucket: str | None = None,
) -> str | None:
    """
    Position label for draft ECR rows (must align with season-stats ``SP`` / ``RP``).

    When FantasyPros is queried with ``position=SP`` or ``position=RP``, the bucket
    wins over ambiguous player metadata (e.g. generic ``P``).
    """
    bucket = str(position_bucket or "").strip().upper()
    if bucket in PITCHER_POSITIONS:
        return bucket

    p = normalize_mlb_position(position)
    if not p or p == LEGACY_PITCHER:
        return None
    if p in PITCHER_POSITIONS:
        return p
    field = normalize_mlb_field_position(p)
    return field or p


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
        "H": "DH",
        "HITTER": "DH",
        "BAT": "DH",
        "B": "DH",
        "TWP": "DH",
        "TW": "DH",
        "TWOWAY": "DH",
        "TWOWAYPLAYER": "DH",
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
        return DEFAULT_HITTER_POSITION
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
            expanded.append(LEGACY_HITTER)
        elif p == LEGACY_PITCHER:
            expanded.extend(PITCHER_POSITIONS)
        elif p in FIELD_POSITIONS:
            expanded.append(p)
        elif p in PITCHER_POSITIONS:
            expanded.append(p)
    if not expanded:
        return None
    return list(dict.fromkeys(expanded))


def is_pitcher_only_selection(positions: list[str] | None) -> bool:
    if not positions:
        return False
    return not any(_is_hitter_pick(p) for p in positions) and any(
        _is_pitcher_pick(p) for p in positions
    )


def is_hitter_only_selection(positions: list[str] | None) -> bool:
    if not positions:
        return False
    return not any(_is_pitcher_pick(p) for p in positions) and any(
        _is_hitter_pick(p) for p in positions
    )


def _hitter_subset(selected: list[str]) -> list[str]:
    field = [p for p in selected if p in FIELD_POSITIONS]
    if field:
        return field
    if LEGACY_HITTER in selected:
        return [LEGACY_HITTER]
    return []


def _pitcher_subset(selected: list[str]) -> list[str]:
    pitchers = [p for p in selected if p in PITCHER_POSITIONS]
    if pitchers:
        return pitchers
    if LEGACY_PITCHER in selected:
        return [LEGACY_PITCHER]
    return []


def _is_pitcher_pick(pos: str) -> bool:
    p = str(pos).strip().upper()
    return p in PITCHER_POSITIONS or p == LEGACY_PITCHER


def _is_hitter_pick(pos: str) -> bool:
    p = str(pos).strip().upper()
    return p in FIELD_POSITIONS or p == LEGACY_HITTER


def coerce_leader_selection(
    selected: list[str] | None,
    previous: list[str] | None = None,
) -> list[str]:
    """
    Season Leaders rules (mirrors NFL K/DST separation):
    - Default → hitters only
    - Pitcher picks (P, SP, RP) cannot mix with hitter picks
    - Adding a pitcher token while on hitters → pitchers only; vice versa
    """
    sel = [
        p
        for p in (selected or [])
        if p in LEADER_POSITIONS or p in (LEGACY_HITTER, LEGACY_PITCHER)
    ]
    prev = list(previous or [])

    if not sel:
        # Match NBA/NHL: clearing the multiselect stays empty (narrow from H/CF tags),
        # not "all field positions" chips.
        return default_leader_selection() if not prev else []

    added = set(sel) - set(prev)
    removed = set(prev) - set(sel)

    if LEGACY_PITCHER in added or any(_is_pitcher_pick(p) for p in added):
        if not any(_is_hitter_pick(p) for p in added):
            return _pitcher_subset(sel)

    if LEGACY_HITTER in added or any(_is_hitter_pick(p) for p in added):
        if not any(_is_pitcher_pick(p) for p in added):
            return _hitter_subset(sel)

    if added & set(PITCHER_POSITIONS) | ({LEGACY_PITCHER} & added):
        if not (added & set(FIELD_POSITIONS)) and LEGACY_HITTER not in added:
            return _pitcher_subset(sel)

    if added & set(FIELD_POSITIONS) | ({LEGACY_HITTER} & added):
        if not (added & set(PITCHER_POSITIONS)) and LEGACY_PITCHER not in added:
            return _hitter_subset(sel)

    if is_pitcher_only_selection(prev) and any(_is_hitter_pick(p) for p in added):
        return _hitter_subset(sel)
    if is_hitter_only_selection(prev) and any(_is_pitcher_pick(p) for p in added):
        return _pitcher_subset(sel)

    if is_pitcher_only_selection(sel):
        return _pitcher_subset(sel)
    if is_hitter_only_selection(sel):
        return _hitter_subset(sel)

    if is_pitcher_only_selection(prev):
        return _pitcher_subset(prev)
    if is_hitter_only_selection(prev):
        return _hitter_subset(prev)

    return sel


# Compare page cohorts (hitters cross-position OK; not vs pitchers).
COMPARE_GROUP_HITTER = "hitter"
COMPARE_GROUP_PITCHER = "pitcher"


def compare_cohort(position: str | None) -> str:
    if is_pitcher_position(position):
        return COMPARE_GROUP_PITCHER
    return COMPARE_GROUP_HITTER


def compare_incompatible_message(cohort_a: str, cohort_b: str) -> str:
    labels = {
        COMPARE_GROUP_HITTER: "hitters",
        COMPARE_GROUP_PITCHER: "pitchers",
    }
    a = labels.get(cohort_a, cohort_a)
    b = labels.get(cohort_b, cohort_b)
    return (
        f"These selections are not comparable: one side is **{a}** and the other is **{b}**. "
        "Compare hitters to hitters or pitchers to pitchers only."
    )
