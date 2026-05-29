"""Regular-season season totals from MLB Stats API (BRef totals often include postseason)."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

from src.sports.mlb.scoring import compute_hitter_fp, compute_pitcher_fp
from src.sports.mlb.seasons import mlb_regular_season_max_games
from src.sports.mlb.teams import normalize_mlb_team, resolve_mlb_team_abbrev
from src.sports.season_type import MLB_REGULAR_GAME_TYPE

_STATS_URL = "https://statsapi.mlb.com/api/v1/stats"
_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"
_PAGE_SIZE = 1000
_REQUEST_DELAY_SEC = 0.15

_HITTING_OVERLAY_COLUMNS: tuple[str, ...] = (
    "games",
    "plate_appearances",
    "runs",
    "home_runs",
    "rbi",
    "stolen_bases",
    "walks",
    "strikeouts_bat",
    "batting_avg",
)

_PITCHING_OVERLAY_COLUMNS: tuple[str, ...] = (
    "games",
    "wins",
    "strikeouts_pitch",
    "saves",
    "innings_pitched",
    "era",
    "whip",
)


def _int_stat(stat: dict[str, Any], *keys: str) -> int:
    for key in keys:
        val = stat.get(key)
        if val is None or val == "":
            continue
        try:
            return int(round(float(val)))
        except (TypeError, ValueError):
            continue
    return 0


def _float_stat(stat: dict[str, Any], *keys: str) -> float:
    for key in keys:
        val = stat.get(key)
        if val is None or val == "":
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return 0.0


def _plate_appearances(stat: dict[str, Any]) -> int:
    pa = _int_stat(stat, "plateAppearances")
    if pa > 0:
        return pa
    ab = _int_stat(stat, "atBats")
    bb = _int_stat(stat, "baseOnBalls", "intentionalWalks")
    hbp = _int_stat(stat, "hitByPitch")
    sf = _int_stat(stat, "sacFlies", "sacrificeFlies")
    return ab + bb + hbp + sf


def _parse_hitting_overlay(stat: dict[str, Any]) -> dict[str, float | int]:
    return {
        "games": _int_stat(stat, "gamesPlayed"),
        "plate_appearances": _plate_appearances(stat),
        "runs": _int_stat(stat, "runs"),
        "home_runs": _int_stat(stat, "homeRuns"),
        "rbi": _int_stat(stat, "rbi"),
        "stolen_bases": _int_stat(stat, "stolenBases"),
        "walks": _int_stat(stat, "baseOnBalls"),
        "strikeouts_bat": _int_stat(stat, "strikeOuts"),
        "batting_avg": _float_stat(stat, "avg"),
    }


def _parse_pitching_overlay(stat: dict[str, Any]) -> dict[str, float | int]:
    return {
        "games": _int_stat(stat, "gamesPlayed"),
        "wins": _int_stat(stat, "wins"),
        "strikeouts_pitch": _int_stat(stat, "strikeOuts"),
        "saves": _int_stat(stat, "saves"),
        "innings_pitched": _float_stat(stat, "inningsPitched"),
        "era": _float_stat(stat, "era"),
        "whip": _float_stat(stat, "whip"),
    }


def _load_team_aliases(season: int) -> dict[str, str]:
    """Normalized team labels -> MLB abbrev (LAD, NYY, …)."""
    resp = requests.get(
        _TEAMS_URL,
        params={"sportId": 1, "season": int(season)},
        timeout=45,
        headers={"User-Agent": "fantasy-tracker/1.0 (mlb-regular-season)"},
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
        headers={"User-Agent": "fantasy-tracker/1.0 (mlb-regular-season)"},
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


def _iter_regular_season_splits(
    season: int,
    *,
    group: str,
) -> list[dict[str, Any]]:
    stat_group = str(group).strip().lower()
    if stat_group not in ("hitting", "pitching"):
        raise ValueError(f"Unsupported group: {group}")

    splits_out: list[dict[str, Any]] = []
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
            headers={"User-Agent": "fantasy-tracker/1.0 (mlb-regular-season)"},
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
        splits_out.extend(splits)
        if len(splits) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
        time.sleep(_REQUEST_DELAY_SEC)
    return splits_out


def _split_to_overlay_row(
    split: dict[str, Any],
    *,
    group: str,
    team_abbrevs: dict[int, str],
) -> dict[str, Any] | None:
    if not isinstance(split, dict):
        return None
    player = split.get("player") or {}
    pid = str(player.get("id") or "").strip()
    if not pid.isdigit():
        return None
    team = split.get("team") or {}
    tid = team.get("id")
    abbrev = team_abbrevs.get(int(tid)) if tid is not None else None
    if not abbrev:
        abbrev = normalize_mlb_team(team.get("name"))
    stat = split.get("stat") or {}
    if not isinstance(stat, dict):
        return None
    parsed = (
        _parse_pitching_overlay(stat)
        if group == "pitching"
        else _parse_hitting_overlay(stat)
    )
    if parsed.get("games", 0) <= 0:
        return None
    row = {"player_id": pid, "team": abbrev, **parsed}
    return row


def fetch_regular_season_stats_frame(
    season: int,
    *,
    group: str,
    aliases: dict[str, str] | None = None,  # noqa: ARG001 — API uses ids; kept for callers
) -> pd.DataFrame:
    """
    Regular-season counting stats per (player_id, team) from MLB Stats API.

    ``group`` is ``hitting`` or ``pitching``.
    """
    _ = aliases
    team_abbrevs = _load_team_abbrev_map(season)
    rows: list[dict[str, Any]] = []
    for split in _iter_regular_season_splits(season, group=group):
        row = _split_to_overlay_row(split, group=group, team_abbrevs=team_abbrevs)
        if row:
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    rate_cols = {"era", "whip", "batting_avg"}
    sum_cols = [
        c
        for c in frame.columns
        if c not in ("player_id", "team") and c not in rate_cols
    ]

    def _combine(group: pd.DataFrame) -> pd.Series:
        out = group[sum_cols].sum(numeric_only=True)
        for col in rate_cols:
            if col in group.columns:
                out[col] = group[col].iloc[-1]
        return out

    return (
        frame.groupby(["player_id", "team"], as_index=False)
        .apply(_combine, include_groups=False)
        .reset_index(drop=True)
    )


def fetch_regular_season_games_map(
    season: int,
    *,
    group: str,
    aliases: dict[str, str] | None = None,
) -> dict[tuple[str, str], int]:
    """``(player_id, team_abbrev) -> gamesPlayed`` for regular season only."""
    frame = fetch_regular_season_stats_frame(season, group=group, aliases=aliases)
    if frame.empty:
        return {}
    out: dict[tuple[str, str], int] = {}
    for _, row in frame.iterrows():
        key = (str(row["player_id"]), str(row["team"]))
        out[key] = int(row.get("games") or 0)
    return out


def _lookup_overlay_row(
    overlay: pd.DataFrame,
    player_id: str,
    team: object,
    *,
    aliases: dict[str, str],
) -> pd.Series | None:
    pid = str(player_id).strip()
    if not pid.isdigit() or overlay.empty:
        return None
    sub = overlay[overlay["player_id"].astype(str) == pid]
    if sub.empty:
        return None
    abbrev = resolve_mlb_team_abbrev(team, aliases)
    if abbrev:
        hit = sub[sub["team"].astype(str).map(normalize_mlb_team) == abbrev]
        if len(hit) == 1:
            return hit.iloc[0]
        if len(hit) > 1:
            return hit.iloc[0]
    norm = normalize_mlb_team(team)
    hit = sub[sub["team"].astype(str).map(normalize_mlb_team) == norm]
    if len(hit) == 1:
        return hit.iloc[0]
    if len(sub) == 1:
        return sub.iloc[0]
    return None


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


def apply_regular_season_overlay(
    frame: pd.DataFrame,
    overlay: pd.DataFrame,
    *,
    season: int,
    group: str,
    aliases: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Replace BRef season totals with MLB Stats API regular-season stats when matched."""
    if frame.empty:
        return frame
    stat_group = str(group).strip().lower()
    cols = (
        _PITCHING_OVERLAY_COLUMNS
        if stat_group == "pitching"
        else _HITTING_OVERLAY_COLUMNS
    )
    if aliases is None:
        aliases = _load_team_aliases(season)
    out = frame.copy()
    cap = mlb_regular_season_max_games(season)
    matched_any = False

    for idx in out.index:
        row = _lookup_overlay_row(
            overlay,
            str(out.loc[idx, "player_id"]),
            out.loc[idx, "team"],
            aliases=aliases,
        )
        if row is not None:
            matched_any = True
            for col in cols:
                if col in out.columns and col in row.index:
                    val = row[col]
                    if col in ("era", "whip", "batting_avg", "innings_pitched"):
                        out.loc[idx, col] = float(val)
                    else:
                        out.loc[idx, col] = int(round(float(val)))
            continue
        if "games" in out.columns:
            games = int(pd.to_numeric(out.loc[idx, "games"], errors="coerce") or 0)
            if games > cap:
                out.loc[idx, "games"] = cap

    if matched_any and "fantasy_points_espn" in out.columns:
        if stat_group == "pitching":
            out["fantasy_points_espn"] = compute_pitcher_fp(out)
        else:
            out["fantasy_points_espn"] = compute_hitter_fp(out)
    return out


def apply_regular_season_games(
    frame: pd.DataFrame,
    games_map: dict[tuple[str, str], int],
    *,
    season: int,
    aliases: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Backward-compatible games-only overlay (prefer :func:`apply_regular_season_overlay`)."""
    if frame.empty:
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


def _aggregate_gamelog_season_stats(
    conn,
    season: int,
    *,
    log_type: str,
) -> pd.DataFrame:
    """Sum regular-season game-log rows (already ``gameType=R`` at ingest)."""
    try:
        exists = conn.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE lower(table_name) = 'mlb_player_game_stats' LIMIT 1
            """
        ).fetchone()
    except Exception:
        return pd.DataFrame()
    if not exists:
        return pd.DataFrame()

    if log_type == "pitching":
        sql = """
            SELECT
                player_id,
                team,
                COUNT(DISTINCT game_id) AS games,
                SUM(COALESCE(wins, 0)) AS wins,
                SUM(COALESCE(strikeouts_pitch, 0)) AS strikeouts_pitch,
                SUM(COALESCE(saves, 0)) AS saves,
                SUM(COALESCE(innings_pitched, 0)) AS innings_pitched
            FROM mlb_player_game_stats
            WHERE season = ? AND log_type = 'pitching'
            GROUP BY player_id, team
        """
    else:
        sql = """
            SELECT
                player_id,
                team,
                COUNT(DISTINCT game_id) AS games,
                SUM(COALESCE(runs, 0)) AS runs,
                SUM(COALESCE(home_runs, 0)) AS home_runs,
                SUM(COALESCE(rbi, 0)) AS rbi,
                SUM(COALESCE(stolen_bases, 0)) AS stolen_bases,
                SUM(COALESCE(walks, 0)) AS walks,
                SUM(COALESCE(strikeouts_bat, 0)) AS strikeouts_bat
            FROM mlb_player_game_stats
            WHERE season = ? AND log_type = 'hitting'
            GROUP BY player_id, team
        """
    df = conn.execute(sql, [int(season)]).df()
    if df.empty:
        return df
    df.columns = [str(c).lower() for c in df.columns]
    df["team"] = df["team"].map(normalize_mlb_team)
    return df


def apply_gamelog_season_overlay(
    conn,
    frame: pd.DataFrame,
    season: int,
    *,
    group: str,
    aliases: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Overlay season totals from ingested regular-season game logs when present."""
    log_type = "pitching" if str(group).strip().lower() == "pitching" else "hitting"
    agg = _aggregate_gamelog_season_stats(conn, season, log_type=log_type)
    if agg.empty:
        return frame
    return apply_regular_season_overlay(
        frame, agg, season=season, group=group, aliases=aliases
    )


def backfill_mlb_regular_season_games(
    conn,
    *,
    seasons: list[int] | None = None,
) -> int:
    """Refresh MLB season stats from regular-season API (+ game logs when available)."""
    if seasons is None:
        rows = conn.execute(
            "SELECT DISTINCT season FROM mlb_player_season_stats ORDER BY season"
        ).fetchall()
        seasons = [int(r[0]) for r in rows]

    updated = 0
    overlay_columns = set(_HITTING_OVERLAY_COLUMNS) | set(_PITCHING_OVERLAY_COLUMNS)
    overlay_columns.add("fantasy_points_espn")

    for year in seasons:
        aliases = _load_team_aliases(year)
        for group in ("hitting", "pitching"):
            pit = group == "pitching"
            pos_filter = (
                "position IN ('SP', 'RP', 'P')"
                if pit
                else "position NOT IN ('SP', 'RP', 'P')"
            )
            df = conn.execute(
                f"""
                SELECT *
                FROM mlb_player_season_stats
                WHERE season = ? AND {pos_filter}
                """,
                [int(year)],
            ).df()
            if df.empty:
                continue
            df.columns = [str(c).lower() for c in df.columns]

            try:
                overlay = fetch_regular_season_stats_frame(
                    year, group=group, aliases=aliases
                )
            except Exception:
                overlay = pd.DataFrame()

            patched = apply_gamelog_season_overlay(
                apply_regular_season_overlay(
                    df, overlay, season=year, group=group, aliases=aliases
                ),
                conn,
                year,
                group=group,
                aliases=aliases,
            )

            for _, row in patched.iterrows():
                orig = df[
                    (df["player_id"].astype(str) == str(row["player_id"]))
                    & (df["position"].astype(str) == str(row["position"]))
                    & (df["team"].astype(str) == str(row["team"]))
                ]
                if orig.empty:
                    continue
                o = orig.iloc[0]
                changed = False
                for col in overlay_columns:
                    if col not in patched.columns:
                        continue
                    new_v = row[col]
                    old_v = o.get(col)
                    if pd.isna(new_v) and pd.isna(old_v):
                        continue
                    try:
                        if float(new_v) == float(old_v):
                            continue
                    except (TypeError, ValueError):
                        if str(new_v) == str(old_v):
                            continue
                    changed = True
                    break
                if not changed:
                    continue
                conn.execute(
                    """
                    UPDATE mlb_player_season_stats
                    SET
                        games = ?,
                        plate_appearances = ?,
                        runs = ?,
                        home_runs = ?,
                        rbi = ?,
                        stolen_bases = ?,
                        walks = ?,
                        strikeouts_bat = ?,
                        batting_avg = ?,
                        wins = ?,
                        strikeouts_pitch = ?,
                        saves = ?,
                        innings_pitched = ?,
                        era = ?,
                        whip = ?,
                        fantasy_points_espn = ?
                    WHERE player_id = ? AND season = ? AND position = ? AND team = ?
                    """,
                    [
                        int(row.get("games") or 0),
                        int(row.get("plate_appearances") or 0),
                        int(row.get("runs") or 0),
                        int(row.get("home_runs") or 0),
                        int(row.get("rbi") or 0),
                        int(row.get("stolen_bases") or 0),
                        int(row.get("walks") or 0),
                        int(row.get("strikeouts_bat") or 0),
                        float(row.get("batting_avg") or 0),
                        int(row.get("wins") or 0),
                        int(row.get("strikeouts_pitch") or 0),
                        int(row.get("saves") or 0),
                        float(row.get("innings_pitched") or 0),
                        float(row.get("era") or 0),
                        float(row.get("whip") or 0),
                        float(row.get("fantasy_points_espn") or 0),
                        str(row["player_id"]),
                        int(year),
                        str(row["position"]),
                        str(row["team"]),
                    ],
                )
                updated += 1
    return updated
