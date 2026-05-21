"""Team D/ST stat columns and nflverse team-stats mapping."""

from __future__ import annotations

DST_STAT_COLUMNS = [
    "sacks",
    "def_interceptions",
    "fumble_recoveries",
    "safeties",
    "blocked_kicks",
    "def_touchdowns",
    "return_touchdowns",
    "points_allowed",
]

# nflverse team stats -> schema
NFLVERSE_TEAM_DST_MAP: dict[str, str] = {
    "team": "team",
    "recent_team": "team",
    "season": "season",
    "week": "week",
    "season_type": "season_type",
    "sacks": "sacks",
    "def_sacks": "sacks",
    "interceptions": "def_interceptions",
    "def_interceptions": "def_interceptions",
    "defensive_interceptions": "def_interceptions",
    "fumble_recovery": "fumble_recoveries",
    "fumble_recoveries": "fumble_recoveries",
    "fumbles_recovered": "fumble_recoveries",
    "def_fumble_recoveries": "fumble_recoveries",
    "safeties": "safeties",
    "def_safeties": "safeties",
    "blocked_kicks": "blocked_kicks",
    "fg_blocked": "blocked_kicks",
    "def_blocked_kicks": "blocked_kicks",
    "def_touchdowns": "def_touchdowns",
    "def_tds": "def_touchdowns",
    "defensive_touchdowns": "def_touchdowns",
    "special_teams_tds": "return_touchdowns",
    "return_touchdowns": "return_touchdowns",
    "return_tds": "return_touchdowns",
    "opponent_score": "points_allowed",
    "opponent_total": "points_allowed",
    "points_allowed": "points_allowed",
    "opp_points": "points_allowed",
    "opp_score": "points_allowed",
}


def sql_dst_stat_select() -> str:
    return ", ".join(DST_STAT_COLUMNS)
