"""MLB team abbreviations from BRef / FanGraphs."""

from __future__ import annotations

import re

# BRef multi-team / season total rows (e.g. 2TM, 3TM, TOT).
_SUMMARY_TEAM_RE = re.compile(r"^(?:\d+TM|TOT|TOTAL)$", re.IGNORECASE)

# Common full-name labels in DB that should resolve to a franchise abbrev.
_CITY_TO_ABBREV: dict[str, str] = {
    "LOS ANGELES": "LAD",
    "LOS ANGELES DODGERS": "LAD",
    "LA DODGERS": "LAD",
    "NEW YORK": "NYY",
    "NEW YORK YANKEES": "NYY",
    "SAN FRANCISCO": "SFG",
    "SAN DIEGO": "SDP",
    "SAN DIEGO PADRES": "SDP",
    "ST LOUIS": "STL",
    "ST. LOUIS": "STL",
    "TAMPA BAY": "TBR",
    "CHICAGO": "CHC",  # ambiguous; prefer ingest codes
    "BOSTON": "BOS",
    "PHILADELPHIA": "PHI",
    "HOUSTON": "HOU",
    "DETROIT": "DET",
    "CLEVELAND": "CLE",
    "MINNESOTA": "MIN",
    "MILWAUKEE": "MIL",
    "CINCINNATI": "CIN",
    "PITTSBURGH": "PIT",
    "COLORADO": "COL",
    "ARIZONA": "ARI",
    "SEATTLE": "SEA",
    "TEXAS": "TEX",
    "TORONTO": "TOR",
    "BALTIMORE": "BAL",
    "KANSAS CITY": "KCR",
    "OAKLAND": "OAK",
    "ATHLETICS": "ATH",
    "MIAMI": "MIA",
    "ATLANTA": "ATL",
    "WASHINGTON": "WSN",
    "CHICAGO WHITE SOX": "CHW",
    "CHICAGO CUBS": "CHC",
    "ANAHEIM": "LAA",
    "LOS ANGELES ANGELS": "LAA",
}


def normalize_mlb_team(team: object) -> str:
    """Trim and uppercase team code; unknown -> UNK."""
    if team is None:
        return "UNK"
    s = str(team).strip().upper()
    if not s or s in ("NAN", "NONE", "<NA>"):
        return "UNK"
    if len(s) <= 4 and s.isalpha():
        return s
    return _CITY_TO_ABBREV.get(s, s)


def resolve_mlb_team_abbrev(team: object, aliases: dict[str, str] | None = None) -> str:
    """Map BRef/FG city names or abbrev to canonical MLB abbrev (e.g. LAD)."""
    raw = str(team or "").strip().upper()
    if not raw or raw in ("NAN", "NONE", "<NA>"):
        return "UNK"
    if aliases and raw in aliases:
        return aliases[raw]
    if raw in _CITY_TO_ABBREV:
        return _CITY_TO_ABBREV[raw]
    if len(raw) <= 4 and raw.isalpha():
        return raw
    if aliases:
        for label, abbrev in aliases.items():
            if label in raw or raw in label:
                return abbrev
    return raw


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
