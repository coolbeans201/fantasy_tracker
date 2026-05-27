"""Fetch and store MLB player game logs."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

from src.sports.mlb.positions import is_pitcher_position
from src.sports.mlb.scoring import compute_hitter_fp, compute_pitcher_fp

_MLB_STATS_URL = "https://statsapi.mlb.com/api/v1/people/{player_id}/stats"


def _season_id(year: int) -> int:
    return int(year)


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _team_abbrev(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return "UNK"
    for key in ("abbreviation", "abbrev", "teamCode", "name"):
        val = payload.get(key)
        if val:
            return str(val)
    return "UNK"


def _extract_rows(player_id: str, player_name: str, end_year: int, payload: dict[str, Any]) -> pd.DataFrame:
    stats = payload.get("stats") or []
    if not isinstance(stats, list):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    season = _season_id(end_year)
    for stat_block in stats:
        splits = stat_block.get("splits") or []
        group = str((stat_block.get("group") or {}).get("displayName", "")).strip().lower()
        if not isinstance(splits, list):
            continue
        for split in splits:
            if not isinstance(split, dict):
                continue
            stat = split.get("stat") or {}
            game = split.get("game") or {}
            team = split.get("team") or {}
            opp = split.get("opponent") or {}
            game_pk = game.get("gamePk") or split.get("gamePk")
            if not game_pk:
                continue
            base = {
                "player_id": str(player_id),
                "player_name": str(player_name),
                "season": season,
                "game_id": str(game_pk),
                "game_date": split.get("date"),
                "team": _team_abbrev(team),
                "opponent": _team_abbrev(opp),
            }
            if group == "pitching":
                row = dict(base)
                row.update(
                    {
                        "wins": _to_float(stat.get("wins")),
                        "strikeouts_pitch": _to_float(stat.get("strikeOuts")),
                        "saves": _to_float(stat.get("saves")),
                        "innings_pitched": _to_float(stat.get("inningsPitched")),
                        "era": _to_float(stat.get("era")),
                    }
                )
                rows.append(row)
            else:
                row = dict(base)
                row.update(
                    {
                        "runs": _to_float(stat.get("runs")),
                        "home_runs": _to_float(stat.get("homeRuns")),
                        "rbi": _to_float(stat.get("rbi")),
                        "stolen_bases": _to_float(stat.get("stolenBases")),
                        "walks": _to_float(stat.get("baseOnBalls")),
                        "strikeouts_bat": _to_float(stat.get("strikeOuts")),
                    }
                )
                rows.append(row)

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["game_date"] = pd.to_datetime(out["game_date"], errors="coerce").dt.date
    out["game_index"] = range(1, len(out) + 1)

    pitching_mask = out["wins"].notna() if "wins" in out.columns else pd.Series(False, index=out.index)
    out["fantasy_points_espn"] = 0.0
    if (~pitching_mask).any():
        out.loc[~pitching_mask, "fantasy_points_espn"] = compute_hitter_fp(out.loc[~pitching_mask])
    if pitching_mask.any():
        out.loc[pitching_mask, "fantasy_points_espn"] = compute_pitcher_fp(out.loc[pitching_mask])

    return out[
        [
            "player_id",
            "player_name",
            "season",
            "game_id",
            "game_date",
            "game_index",
            "team",
            "opponent",
            "fantasy_points_espn",
        ]
    ]


def fetch_player_gamelog(
    player_id: str, player_name: str, end_year: int, *, is_pitcher: bool
) -> pd.DataFrame:
    params = {
        "stats": "gameLog",
        "group": "pitching" if is_pitcher else "hitting",
        "season": int(end_year),
    }
    resp = requests.get(
        _MLB_STATS_URL.format(player_id=player_id),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    return _extract_rows(player_id, player_name, end_year, payload)


def ingest_season_gamelogs(
    conn,
    end_year: int,
    *,
    limit_players: int | None = None,
    delay_sec: float = 0.25,
) -> int:
    """Ingest MLB game logs for one season (hitters and pitchers)."""
    q = """
        SELECT player_id, player_name, position
        FROM mlb_player_season_stats
        WHERE season = ?
        ORDER BY player_id
    """
    params: list[Any] = [end_year]
    if limit_players:
        q += " LIMIT ?"
        params.append(int(limit_players))
    players = conn.execute(q, params).df()
    if players.empty:
        return 0

    # Players can appear in multiple season rows (team splits / position splits).
    # Build one ingest record per player_id and keep pitcher flag if any row is pitcher.
    by_player: dict[str, dict[str, Any]] = {}
    for _, row in players.iterrows():
        pid = str(row["player_id"]).strip()
        if not pid:
            continue
        entry = by_player.get(pid)
        if entry is None:
            entry = {
                "player_name": str(row.get("player_name") or "").strip(),
                "is_pitcher": False,
            }
            by_player[pid] = entry
        pos = str(row.get("position") or "").strip()
        if is_pitcher_position(pos):
            entry["is_pitcher"] = True

    conn.execute("DELETE FROM mlb_player_game_stats WHERE season = ?", [end_year])
    total = 0
    for pid in sorted(by_player):
        if not pid.isdigit():
            continue
        meta = by_player[pid]
        pname = str(meta.get("player_name") or "").strip()
        is_pitcher = bool(meta.get("is_pitcher"))
        try:
            frame = fetch_player_gamelog(pid, pname, end_year, is_pitcher=is_pitcher)
        except Exception:
            time.sleep(delay_sec)
            continue
        if frame.empty:
            time.sleep(delay_sec)
            continue
        frame = frame.drop_duplicates(subset=["player_id", "season", "game_id"], keep="first")
        conn.register("_mlb_g", frame)
        conn.execute("INSERT INTO mlb_player_game_stats SELECT * FROM _mlb_g")
        conn.unregister("_mlb_g")
        total += len(frame)
        time.sleep(delay_sec)
    return total
