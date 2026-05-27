"""Fetch and store NHL player game logs."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

from src.sports.game_logs import order_game_log_by_date
from src.sports.nhl.positions import is_goalie_position
from src.sports.nhl.scoring import compute_skater_fp

NHL_GAMELOG_RETRIES = 4
NHL_GAMELOG_BASE_DELAY_SEC = 1.0


def _season_id(end_year: int) -> str:
    return f"{end_year - 1}{end_year}"


def _val(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return default


def fetch_player_gamelog(player_id: str, player_name: str, end_year: int) -> pd.DataFrame:
    season_id = _season_id(end_year)
    url = f"https://api-web.nhle.com/v1/player/{player_id}/game-log/{season_id}/2"
    last: Exception | None = None
    for attempt in range(1, NHL_GAMELOG_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            break
        except Exception as exc:
            last = exc
            if attempt >= NHL_GAMELOG_RETRIES:
                raise
            wait = NHL_GAMELOG_BASE_DELAY_SEC * attempt
            print(f"  NHL gamelog {player_id} failed ({exc}); retrying in {wait:.1f}s...")
            time.sleep(wait)
    else:
        if last is not None:
            raise last
        return pd.DataFrame()
    games = payload.get("gameLog") or payload.get("games") or []
    if not isinstance(games, list) or not games:
        return pd.DataFrame()

    out = pd.DataFrame(
        [
            {
                "player_id": str(player_id),
                "player_name": str(player_name),
                "season": int(end_year),
                "game_id": str(_val(g, "gameId", "game_id", "id", default="")),
                "game_date": _val(g, "gameDate", "game_date"),
                "team": str(_val(g, "teamAbbrev", "team", default="UNK")),
                "opponent": str(_val(g, "opponentAbbrev", "opponent", default="UNK")),
                "goals": _val(g, "goals", default=0),
                "assists": _val(g, "assists", default=0),
                "points": _val(g, "points", default=0),
                "shots": _val(g, "shots", "shotsOnGoal", default=0),
            }
            for g in games
        ]
    )
    out = out[out["game_id"].astype(str).str.len() > 0].copy()
    if out.empty:
        return out
    out["game_date"] = pd.to_datetime(out["game_date"], errors="coerce").dt.date
    out = order_game_log_by_date(out)
    for c in ("goals", "assists", "points", "shots"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
    out["fantasy_points_espn"] = compute_skater_fp(out)
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
            "goals",
            "assists",
            "points",
            "shots",
            "fantasy_points_espn",
        ]
    ]


def ingest_season_gamelogs(
    conn,
    end_year: int,
    *,
    limit_players: int | None = None,
    delay_sec: float = 0.25,
) -> dict[str, int]:
    """Ingest NHL skater game logs for one season."""
    q = """
        SELECT DISTINCT player_id, player_name, position
        FROM nhl_player_season_stats
        WHERE season = ?
        ORDER BY player_id
    """
    params: list[Any] = [end_year]
    if limit_players:
        q += " LIMIT ?"
        params.append(int(limit_players))
    players = conn.execute(q, params).df()
    if players.empty:
        return {"rows": 0, "players_total": 0, "players_loaded": 0, "players_skipped": 0}

    conn.execute("DELETE FROM nhl_player_game_stats WHERE season = ?", [end_year])
    total = 0
    loaded = 0
    skipped = 0
    for _, row in players.iterrows():
        pos = str(row.get("position") or "").strip()
        if is_goalie_position(pos):
            skipped += 1
            continue
        pid = str(row["player_id"]).strip()
        if not pid or pid.lower() in {"nan", "none", "<na>"}:
            skipped += 1
            continue
        pname = str(row.get("player_name") or "").strip()
        try:
            frame = fetch_player_gamelog(pid, pname, end_year)
        except Exception:
            skipped += 1
            time.sleep(delay_sec)
            continue
        if frame.empty:
            skipped += 1
            time.sleep(delay_sec)
            continue
        frame["player_id"] = frame["player_id"].astype(str).str.strip()
        frame["game_id"] = frame["game_id"].astype(str).str.strip()
        frame = frame[
            frame["player_id"].ne("")
            & frame["player_id"].str.lower().ne("nan")
            & frame["player_id"].str.lower().ne("none")
            & frame["player_id"].str.lower().ne("<na>")
            & frame["game_id"].ne("")
            & frame["game_id"].str.lower().ne("nan")
            & frame["game_id"].str.lower().ne("none")
            & frame["game_id"].str.lower().ne("<na>")
        ]
        frame = frame.drop_duplicates(subset=["player_id", "season", "game_id"], keep="first")
        if frame.empty:
            skipped += 1
            time.sleep(delay_sec)
            continue
        conn.register("_nhl_g", frame)
        conn.execute("INSERT INTO nhl_player_game_stats SELECT * FROM _nhl_g")
        conn.unregister("_nhl_g")
        total += len(frame)
        loaded += 1
        time.sleep(delay_sec)
    return {
        "rows": int(total),
        "players_total": int(len(players)),
        "players_loaded": int(loaded),
        "players_skipped": int(skipped),
    }
