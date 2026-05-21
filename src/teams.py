"""NFL team abbreviations, display names, and search aliases."""

from __future__ import annotations

# Current and legacy nflverse team codes with searchable metadata.
_TEAM_CATALOG: list[dict[str, str | tuple[str, ...]]] = [
    {
        "abbr": "ARI",
        "city": "Arizona",
        "nickname": "Cardinals",
        "aliases": ("cardinal", "arizona cardinal", "phx", "phoenix", "stl", "st louis"),
    },
    {
        "abbr": "ATL",
        "city": "Atlanta",
        "nickname": "Falcons",
        "aliases": ("falcon", "atlanta falcon"),
    },
    {
        "abbr": "BAL",
        "city": "Baltimore",
        "nickname": "Ravens",
        "aliases": ("raven", "baltimore raven"),
    },
    {
        "abbr": "BUF",
        "city": "Buffalo",
        "nickname": "Bills",
        "aliases": ("bill", "buffalo bill"),
    },
    {
        "abbr": "CAR",
        "city": "Carolina",
        "nickname": "Panthers",
        "aliases": ("panther", "carolina panther"),
    },
    {
        "abbr": "CHI",
        "city": "Chicago",
        "nickname": "Bears",
        "aliases": ("bear", "chicago bear"),
    },
    {
        "abbr": "CIN",
        "city": "Cincinnati",
        "nickname": "Bengals",
        "aliases": ("bengal", "cincinnati bengal"),
    },
    {
        "abbr": "CLE",
        "city": "Cleveland",
        "nickname": "Browns",
        "aliases": ("brown", "cleveland brown"),
    },
    {
        "abbr": "DAL",
        "city": "Dallas",
        "nickname": "Cowboys",
        "aliases": ("cowboy", "dallas cowboy"),
    },
    {
        "abbr": "DEN",
        "city": "Denver",
        "nickname": "Broncos",
        "aliases": ("bronco", "denver bronco"),
    },
    {
        "abbr": "DET",
        "city": "Detroit",
        "nickname": "Lions",
        "aliases": ("lion", "detroit lion"),
    },
    {
        "abbr": "GB",
        "city": "Green Bay",
        "nickname": "Packers",
        "aliases": ("packer", "green bay packer", "gnb"),
    },
    {
        "abbr": "HOU",
        "city": "Houston",
        "nickname": "Texans",
        "aliases": ("texan", "houston texan"),
    },
    {
        "abbr": "IND",
        "city": "Indianapolis",
        "nickname": "Colts",
        "aliases": ("colt", "indianapolis colt"),
    },
    {
        "abbr": "JAX",
        "city": "Jacksonville",
        "nickname": "Jaguars",
        "aliases": ("jaguar", "jacksonville jaguar", "jac"),
    },
    {
        "abbr": "KC",
        "city": "Kansas City",
        "nickname": "Chiefs",
        "aliases": ("chief", "kansas city chief"),
    },
    {
        "abbr": "LAC",
        "city": "Los Angeles",
        "nickname": "Chargers",
        "aliases": ("charger", "la charger", "los angeles charger", "sd", "san diego"),
    },
    {
        "abbr": "LAR",
        "city": "Los Angeles",
        "nickname": "Rams",
        "aliases": ("ram", "la ram", "los angeles ram", "stl rams"),
    },
    {
        "abbr": "LV",
        "city": "Las Vegas",
        "nickname": "Raiders",
        "aliases": ("raider", "las vegas raider", "oak", "oakland", "lvr"),
    },
    {
        "abbr": "MIA",
        "city": "Miami",
        "nickname": "Dolphins",
        "aliases": ("dolphin", "miami dolphin"),
    },
    {
        "abbr": "MIN",
        "city": "Minnesota",
        "nickname": "Vikings",
        "aliases": ("viking", "minnesota viking"),
    },
    {
        "abbr": "NE",
        "city": "New England",
        "nickname": "Patriots",
        "aliases": ("patriot", "new england patriot", "nwe"),
    },
    {
        "abbr": "NO",
        "city": "New Orleans",
        "nickname": "Saints",
        "aliases": ("saint", "new orleans saint", "norf", "nor"),
    },
    {
        "abbr": "NYG",
        "city": "New York",
        "nickname": "Giants",
        "aliases": ("giant", "ny giants", "nyg giants"),
    },
    {
        "abbr": "NYJ",
        "city": "New York",
        "nickname": "Jets",
        "aliases": ("jet", "ny jets", "nyj jets"),
    },
    {
        "abbr": "PHI",
        "city": "Philadelphia",
        "nickname": "Eagles",
        "aliases": ("eagle", "philadelphia eagle"),
    },
    {
        "abbr": "PIT",
        "city": "Pittsburgh",
        "nickname": "Steelers",
        "aliases": ("steeler", "pittsburgh steeler"),
    },
    {
        "abbr": "SEA",
        "city": "Seattle",
        "nickname": "Seahawks",
        "aliases": ("seahawk", "seattle seahawk"),
    },
    {
        "abbr": "SF",
        "city": "San Francisco",
        "nickname": "49ers",
        "aliases": ("49er", "niners", "niner", "san francisco 49er", "sfo"),
    },
    {
        "abbr": "TB",
        "city": "Tampa Bay",
        "nickname": "Buccaneers",
        "aliases": ("buccaneer", "bucs", "buc", "tampa bay buccaneer"),
    },
    {
        "abbr": "TEN",
        "city": "Tennessee",
        "nickname": "Titans",
        "aliases": ("titan", "tennessee titan", "oti"),
    },
    {
        "abbr": "WAS",
        "city": "Washington",
        "nickname": "Commanders",
        "aliases": (
            "commander",
            "redskin",
            "redskins",
            "football team",
            "wft",
            "wsh",
            "washington football",
        ),
    },
]

# Legacy codes that appear in older nflverse seasons
_LEGACY_ABBR: dict[str, str] = {
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
    "PHO": "ARI",
    "PHX": "ARI",
    "RAI": "LV",
    "GNB": "GB",
    "NOR": "NO",
    "NWE": "NE",
    "SFO": "SF",
    "TAM": "TB",
    "KAN": "KC",
    "CLT": "IND",
    "CRD": "ARI",
    "RAM": "LAR",
    "SDG": "LAC",
}

_BY_ABBR: dict[str, dict] = {t["abbr"]: t for t in _TEAM_CATALOG}


def team_full_name(abbr: str) -> str:
    """e.g. ARI -> Arizona Cardinals."""
    code = str(abbr).strip().upper()
    meta = _BY_ABBR.get(code)
    if meta:
        return f"{meta['city']} {meta['nickname']}"
    legacy = _LEGACY_ABBR.get(code)
    if legacy:
        return team_full_name(legacy)
    return code


def dst_entity_display_name(abbr: str) -> str:
    """Label for search results and profile header."""
    code = str(abbr).strip().upper()
    return f"{team_full_name(code)} ({code})"


def _search_blob(meta: dict) -> str:
    parts = [
        meta["abbr"],
        meta["city"],
        meta["nickname"],
        f"{meta['city']} {meta['nickname']}",
        *meta.get("aliases", ()),
    ]
    return " ".join(str(p).lower() for p in parts)


def team_codes_matching_query(query: str) -> list[str]:
    """
    Resolve a search string to nflverse team abbreviation(s).
    Matches city, nickname, full name, abbr, and aliases (substring).
    """
    q = query.strip().lower()
    if not q:
        return []

    codes: list[str] = []
    for meta in _TEAM_CATALOG:
        blob = _search_blob(meta)
        if q in blob or any(q in str(a).lower() for a in meta.get("aliases", ())):
            codes.append(meta["abbr"])

    # Direct abbreviation match (e.g. "ari")
    for meta in _TEAM_CATALOG:
        abbr = meta["abbr"].lower()
        if abbr == q or abbr.startswith(q):
            if meta["abbr"] not in codes:
                codes.append(meta["abbr"])

    for legacy, current in _LEGACY_ABBR.items():
        if legacy.lower() == q and current not in codes:
            codes.append(current)

    expanded = list(codes)
    for legacy, current in _LEGACY_ABBR.items():
        if current in codes and legacy not in expanded:
            expanded.append(legacy)
    return expanded


def team_search_patterns(query: str) -> tuple[str, list[str]]:
    """
    Return (ILIKE pattern for SQL, team codes for IN clause).
    """
    pattern = f"%{query.strip()}%"
    codes = team_codes_matching_query(query)
    return pattern, codes
