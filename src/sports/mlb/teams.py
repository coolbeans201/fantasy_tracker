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
