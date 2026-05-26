"""NHL team abbreviations from NHL.com stats API."""

from __future__ import annotations

import re

# Season-total rows when the API also returns per-team stints.
_SUMMARY_TEAM_RE = re.compile(r"^(?:\d+TM|TOT|TOTAL|NHL)$", re.IGNORECASE)


def normalize_nhl_team(team: object) -> str:
    """Trim and uppercase a single franchise code; unknown -> UNK."""
    if team is None:
        return "UNK"
    s = str(team).strip().upper()
    if not s or s in ("NAN", "NONE", "<NA>"):
        return "UNK"
    # API sometimes uses "T.B" style — keep dots out for filters.
    return s.replace(".", "")


def is_summary_team(team: object) -> bool:
    return bool(_SUMMARY_TEAM_RE.match(normalize_nhl_team(team)))


def is_combined_team_label(team: object) -> bool:
    """True when the label lists multiple franchises (comma/slash), not one team."""
    raw = str(team or "").strip()
    if not raw:
        return False
    if is_summary_team(raw):
        return True
    return any(sep in raw for sep in (",", "/", "|"))
