"""Regular-season games played from MLB Stats API (BRef G often includes postseason)."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

from src.sports.mlb.seasons import mlb_regular_season_max_games
from src.sports.mlb.teams import normalize_mlb_team, resolve_mlb_team_abbrev
from src.sports.season_type import MLB_REGULAR_GAME_TYPE

_STATS_URL = "https://statsapi.mlb.com/api/v1/stats"
_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"
_PAGE_SIZE = 1000
_REQUEST_DELAY_SEC = 0.15


def _load_team_aliases(season: int) -> dict[str, str]:
    """Normalized team labels -> MLB abbrev (LAD, NYY, …)."""
    resp = requests.get(
        _TEAMS_URL,
        params={"sportId": 1, "season": int(season)},
        timeout=45,
        headers={"User-Agent": "fantasy-tracker/1.0 (mlb-season-games)"},
    )
    resp.raise_for_status()
    teams = resp.json().get("teams") or []
    aliases: dict[str, str] = {}
    for team in teams:
        if not isinstance(team, dict):
            continue
        abbrev = normalize_mlb_team(team.get("abbreviation"))
        if not abbrev or abbrev == "UNK":
            continue
        labels = [
            abbrev,
            team.get("abbreviation"),
            team.get("teamCode"),
            team.get("fileCode"),
            team.get("teamName"),
            team.get("clubName"),
            team.get("locationName"),
            team.get("name"),
            team.get("shortName"),
        ]
        loc = str(team.get("locationName") or "").strip()
        club = str(team.get("clubName") or team.get("teamName") or "").strip()
        if loc and club:
            labels.append(f"{loc} {club}")
        if loc:
            labels.append(loc)
        for label in labels:
            if not label:
                continue
            aliases[normalize_mlb_team(label)] = abbrev
    return aliases


def _load_team_abbrev_map(season: int) -> dict[int, str]:
    resp = requests.get(
        _TEAMS_URL,
        params={"sportId": 1, "season": int(season)},
        timeout=45,
        headers={"User-Agent": "fantasy-tracker/1.0 (mlb-season-games)"},
    )
    resp.raise_for_status()
    teams = resp.json().get("teams") or []
    out: dict[int, str] = {}
    for team in teams:
        if not isinstance(team, dict):
            continue
        tid = team.get("id")
        abbrev = team.get("abbreviation")
        if tid is not None and abbrev:
            out[int(tid)] = normalize_mlb_team(abbrev)
    return out


def _lookup_regular_season_games(
    games_map: dict[tuple[str, str], int],
    player_id: str,
    team: object,
    *,
    aliases: dict[str, str],
) -> int | None:
    pid = str(player_id).strip()
    if not pid.isdigit():
        return None
    abbrev = resolve_mlb_team_abbrev(team, aliases)
    for key in ((pid, abbrev), (pid, normalize_mlb_team(team))):
        if key in games_map:
            return int(games_map[key])
    player_keys = [g for (p, _t), g in games_map.items() if p == pid]
    if len(player_keys) == 1:
        return int(player_keys[0])
    return None


def fetch_regular_season_games_map(
    season: int,
    *,
    group: str,
    aliases: dict[str, str] | None = None,
) -> dict[tuple[str, str], int]:
    """
    ``(player_id, team_abbrev) -> gamesPlayed`` for regular season only.

    ``group`` is ``hitting`` or ``pitching``.
    """
    stat_group = str(group).strip().lower()
    if stat_group not in ("hitting", "pitching"):
        raise ValueError(f"Unsupported group: {group}")

    team_abbrevs = _load_team_abbrev_map(season)
    if aliases is None:
        aliases = _load_team_aliases(season)
    out: dict[tuple[str, str], int] = {}
    offset = 0

    while True:
        resp = requests.get(
            _STATS_URL,
            params={
                "stats": "season",
                "group": stat_group,
                "season": int(season),
                "gameType": MLB_REGULAR_GAME_TYPE,
                "playerPool": "ALL",
                "limit": _PAGE_SIZE,
                "offset": offset,
            },
            timeout=60,
            headers={"User-Agent": "fantasy-tracker/1.0 (mlb-season-games)"},
        )
        resp.raise_for_status()
        payload = resp.json()
        stats = payload.get("stats") or []
        splits: list[dict[str, Any]] = []
        if stats and isinstance(stats[0], dict):
            raw = stats[0].get("splits")
            if isinstance(raw, list):
                splits = raw
        if not splits:
            break

        for split in splits:
            if not isinstance(split, dict):
                continue
            player = split.get("player") or {}
            pid = str(player.get("id") or "").strip()
            if not pid.isdigit():
                continue
            team = split.get("team") or {}
            tid = team.get("id")
            abbrev = team_abbrevs.get(int(tid)) if tid is not None else None
            if not abbrev:
                abbrev = normalize_mlb_team(team.get("name"))
            stat = split.get("stat") or {}
            gp = stat.get("gamesPlayed")
            try:
                games = int(gp)
            except (TypeError, ValueError):
                continue
            key = (pid, abbrev)
            out[key] = out.get(key, 0) + games

        if len(splits) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
        time.sleep(_REQUEST_DELAY_SEC)

    return out


def apply_regular_season_games(
    frame: pd.DataFrame,
    games_map: dict[tuple[str, str], int],
    *,
    season: int,
    aliases: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Replace inflated BRef ``G`` with MLB regular-season games when matched."""
    if frame.empty or "games" not in frame.columns:
        return frame
    if aliases is None:
        aliases = _load_team_aliases(season)
    out = frame.copy()
    cap = mlb_regular_season_max_games(season)
    for idx in out.index:
        pid = str(out.loc[idx, "player_id"]).strip()
        games = int(pd.to_numeric(out.loc[idx, "games"], errors="coerce") or 0)
        matched = _lookup_regular_season_games(
            games_map, pid, out.loc[idx, "team"], aliases=aliases
        )
        if matched is not None:
            games = matched
        elif games > cap:
            games = cap
        out.loc[idx, "games"] = int(games)
    return out


def backfill_mlb_regular_season_games(
    conn,
    *,
    seasons: list[int] | None = None,
) -> int:
    """Update ``games`` on ``mlb_player_season_stats`` from MLB Stats API. Returns rows touched."""
    if seasons is None:
        rows = conn.execute(
            "SELECT DISTINCT season FROM mlb_player_season_stats ORDER BY season"
        ).fetchall()
        seasons = [int(r[0]) for r in rows]

    updated = 0
    for year in seasons:
        aliases = _load_team_aliases(year)
        for group in ("hitting", "pitching"):
            try:
                games_map = fetch_regular_season_games_map(
                    year, group=group, aliases=aliases
                )
            except Exception:
                continue
            if not games_map:
                continue
            pit = group == "pitching"
            pos_filter = (
                "position IN ('SP', 'RP', 'P')"
                if pit
                else "position NOT IN ('SP', 'RP', 'P')"
            )
            df = conn.execute(
                f"""
                SELECT player_id, season, position, team, games
                FROM mlb_player_season_stats
                WHERE season = ? AND {pos_filter}
                """,
                [int(year)],
            ).df()
            if df.empty:
                continue
            df.columns = [str(c).lower() for c in df.columns]
            for _, row in df.iterrows():
                pid = str(row["player_id"]).strip()
                matched = _lookup_regular_season_games(
                    games_map, pid, row["team"], aliases=aliases
                )
                if matched is None:
                    continue
                new_g = int(matched)
                old_g = int(row["games"] or 0)
                if new_g == old_g:
                    continue
                conn.execute(
                    """
                    UPDATE mlb_player_season_stats
                    SET games = ?
                    WHERE player_id = ? AND season = ? AND position = ? AND team = ?
                    """,
                    [
                        new_g,
                        pid,
                        int(year),
                        str(row["position"]),
                        str(row["team"]),
                    ],
                )
                updated += 1
    return updated
