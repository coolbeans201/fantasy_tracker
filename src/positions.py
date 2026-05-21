"""Fantasy position normalization (skill positions only)."""

from __future__ import annotations

# Offensive skill positions for fantasy (ingest + UI)
FANTASY_POSITIONS = ["QB", "RB", "WR", "TE"]
_ALLOWED_POSITIONS = frozenset(FANTASY_POSITIONS)

# Map alternate labels to fantasy lineup positions before allowlist check
_POSITION_ALIASES: dict[str, str] = {
    "FB": "RB",
    "HB": "RB",
}


def normalize_fantasy_position(position: str | None) -> str | None:
    """
    Return fantasy lineup position, or None if not a skill position we track.
    QB, WR, TE, and RB family (RB/HB/FB) only — excludes defense, K, OL, etc.
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
    """True if position is QB, RB (incl. HB/FB), WR, or TE."""
    return normalize_fantasy_position(position) is not None


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
    return normalize_fantasy_position(position)
