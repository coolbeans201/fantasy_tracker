"""NBA team codes for cross-source matching (FantasyPros vs nba_api)."""

from __future__ import annotations

# FantasyPros / legacy labels → nba_api TEAM_ABBREVIATION seen in season stats.
_FP_TO_STATS: dict[str, str] = {
    "PHO": "PHX",
    "BRK": "BKN",
    "BRO": "BKN",
    "NJN": "BKN",
    "NOH": "NOP",
    "NOK": "NOP",
    "CHA": "CHA",
    "CHH": "CHA",
    "CHO": "CHA",
    "VAN": "MEM",
    "WSH": "WAS",
    "SAN": "SAS",
}


def nba_team_match_candidates(team: str | None, valid_teams: set[str]) -> list[str]:
    """
    Return team codes to try when narrowing a name match pool.

    If none of the candidates appear in ``valid_teams``, callers should skip team filtering.
    """
    if not team:
        return []
    raw = str(team).strip().upper()
    if not raw or raw in ("UNK", "NAN", "FA", "ALL"):
        return []
    candidates: list[str] = []
    for code in (raw, _FP_TO_STATS.get(raw, "")):
        if code and code in valid_teams and code not in candidates:
            candidates.append(code)
    return candidates
