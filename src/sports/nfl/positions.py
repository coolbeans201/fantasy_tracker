"""Fantasy position normalization (skill positions only)."""

from __future__ import annotations

# Player positions for fantasy (ingest + UI). DST is a separate team-level entity.
FANTASY_POSITIONS = ["QB", "RB", "WR", "TE", "K"]
OFFENSE_POSITIONS = ["QB", "RB", "WR", "TE"]
DST_POSITION = "DST"
_LEADER_POSITIONS = FANTASY_POSITIONS + [DST_POSITION]
_ALLOWED_POSITIONS = frozenset(FANTASY_POSITIONS)

# Map alternate labels to fantasy lineup positions before allowlist check
_POSITION_ALIASES: dict[str, str] = {
    "FB": "RB",
    "HB": "RB",
}


def normalize_fantasy_position(position: str | None) -> str | None:
    """
    Return fantasy lineup position, or None if not a skill position we track.
    QB, WR, TE, RB family (RB/HB/FB), and K — excludes individual defenders, OL, etc.
    """
    if position is None or (isinstance(position, float) and str(position) == "nan"):
        return None
    pos = str(position).strip().upper()
    if not pos:
        return None
    pos = _POSITION_ALIASES.get(pos, pos)
    if pos not in _ALLOWED_POSITIONS:
        return None
    return pos


def is_fantasy_skill_position(position: str | None) -> bool:
    """True if position is QB, RB (incl. HB/FB), WR, TE, or K."""
    return normalize_fantasy_position(position) is not None


def is_dst_position(position: str | None) -> bool:
    return str(position or "").strip().upper() == DST_POSITION


def leader_position_options() -> list[str]:
    """Positions shown in Season Leaders filter."""
    return list(_LEADER_POSITIONS)


def is_kicker_only_selection(positions: list[str] | None) -> bool:
    return positions == ["K"]


def is_dst_only_selection(positions: list[str] | None) -> bool:
    return positions == [DST_POSITION]


def _offense_subset(selected: list[str]) -> list[str]:
    offense = [p for p in selected if p in OFFENSE_POSITIONS]
    return offense or list(OFFENSE_POSITIONS)


def coerce_leader_selection(
    selected: list[str] | None,
    previous: list[str] | None = None,
) -> list[str]:
    """
    Season Leaders position filter rules:
    - Default / empty → offense only (QB–TE)
    - K or DST alone — not combined with other positions
    - Switching away from K/DST: picking an offensive position drops the special view
    """
    sel = list(selected or [])
    prev = list(previous or [])

    if not sel:
        return list(OFFENSE_POSITIONS)

    added = set(sel) - set(prev)
    removed = set(prev) - set(sel)

    if DST_POSITION in added:
        return [DST_POSITION]
    if "K" in added:
        return ["K"]

    if added & set(OFFENSE_POSITIONS) and prev in ([DST_POSITION], ["K"]):
        return _offense_subset(sel)

    if DST_POSITION in removed or "K" in removed:
        return _offense_subset(sel)

    if sel == [DST_POSITION]:
        return [DST_POSITION]
    if sel == ["K"]:
        return ["K"]

    if DST_POSITION in sel or "K" in sel:
        offense = [p for p in sel if p in OFFENSE_POSITIONS]
        if offense:
            return offense
        return [DST_POSITION] if DST_POSITION in sel else ["K"]

    return _offense_subset(sel)


def normalize_leader_selection(selected: list[str] | None) -> list[str]:
    """Normalize leader selection without prior widget state (e.g. SQL filters)."""
    return coerce_leader_selection(selected, previous=None)


def expand_position_filter(positions: list[str] | None) -> list[str] | None:
    """
    Expand UI position filters for SQL IN clauses.
    Selecting RB also matches legacy FB rows not yet re-ingested.
    """
    if not positions:
        return None
    expanded: set[str] = set()
    for p in positions:
        norm = normalize_fantasy_position(p) or p
        expanded.add(norm)
        if norm == "RB":
            expanded.add("FB")
    return sorted(expanded)


def positions_for_peer_grouping(position: str | None) -> str | None:
    """Position key used for peer Z-score cohorts."""
    if is_dst_position(position):
        return DST_POSITION
    return normalize_fantasy_position(position)


# Compare page cohorts: offense cross-position OK; K and DST only vs same cohort.
COMPARE_GROUP_OFFENSE = "offense"
COMPARE_GROUP_KICKER = "kicker"
COMPARE_GROUP_DST = "dst"


def compare_cohort(entity_id: str | None = None, position: str | None = None) -> str:
    """
    Cohort for apples-to-apples comparisons on the Compare page.
    Uses entity_id (dst:TEAM) and/or stored position label.
    """
    from src.entities import is_dst_entity

    if is_dst_entity(entity_id) or is_dst_position(position):
        return COMPARE_GROUP_DST
    pos = normalize_fantasy_position(position)
    if pos == "K":
        return COMPARE_GROUP_KICKER
    return COMPARE_GROUP_OFFENSE


def compare_cohorts_compatible(cohort_a: str, cohort_b: str) -> bool:
    return cohort_a == cohort_b


def compare_incompatible_message(cohort_a: str, cohort_b: str) -> str:
    """User-facing explanation when two selections cannot be compared."""
    labels = {
        COMPARE_GROUP_OFFENSE: "offensive players (QB, RB, WR, TE)",
        COMPARE_GROUP_KICKER: "kickers",
        COMPARE_GROUP_DST: "team defenses (DST)",
    }
    a = labels.get(cohort_a, cohort_a)
    b = labels.get(cohort_b, cohort_b)
    return (
        f"These selections are not comparable: one side is **{a}** and the other is **{b}**. "
        f"Offensive positions can be compared to each other, but kickers should only be "
        f"compared to kickers and defenses only to defenses."
    )
