"""MLB team abbreviations from BRef / FanGraphs."""

from __future__ import annotations

import re

# BRef multi-team / season total rows (e.g. 2TM, 3TM, TOT).
_SUMMARY_TEAM_RE = re.compile(r"^(?:\d+TM|TOT|TOTAL)$", re.IGNORECASE)


def normalize_mlb_team(team: object) -> str:
    """Trim and uppercase team code; unknown -> UNK."""
    if team is None:
        return "UNK"
    s = str(team).strip().upper()
    return s if s and s not in ("NAN", "NONE", "<NA>") else "UNK"


def is_summary_team(team: object) -> bool:
    """True for combined-season rows (2TM, TOT, …), not a single franchise."""
    return bool(_SUMMARY_TEAM_RE.match(normalize_mlb_team(team)))


def is_combined_team_label(team: object) -> bool:
    """
    True when the label represents multiple franchises, not a single team code.
    Examples: ``2TM``, ``TOT``, ``LAD/CHC``, ``NYY,SEA``.
    """
    raw = str(team or "").strip()
    if not raw:
        return False
    if is_summary_team(raw):
        return True
    return any(sep in raw for sep in ("/", ",", "|"))
