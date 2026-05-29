"""Fetch and store NHL player game logs (skaters and goalies)."""

from __future__ import annotations

import threading
import time
from typing import Any

import pandas as pd
import requests

from src.db.sport_schema import NHL_PLAYER_GAME_COLUMNS
from src.sports.game_logs import order_game_log_by_date
from src.sports.nhl.positions import is_goalie_position
from src.sports.nhl.scoring import compute_goalie_fp, compute_skater_fp
from src.sports.season_type import filter_nhl_gamelog_games

NHL_LOG_SKATER = "skater"
NHL_LOG_GOALIE = "goalie"

NHL_GAMELOG_RETRIES = 7
NHL_GAMELOG_BASE_DELAY_SEC = 2.0
NHL_GAMELOG_429_BACKOFF_CAP_SEC = 90.0
NHL_GAMELOG_DEFAULT_WORKERS = 3
NHL_GAMELOG_DEFAULT_DELAY_SEC = 0.65

_throttle_lock = threading.Lock()
_throttle_last_request = 0.0
_throttle_min_interval_sec = NHL_GAMELOG_DEFAULT_DELAY_SEC


def configure_nhl_gamelog_throttle(min_interval_sec: float) -> None:
    """Global spacing between api-web.nhle.com requests (all worker threads)."""
    global _throttle_min_interval_sec
    _throttle_min_interval_sec = max(0.0, float(min_interval_sec))


def _throttle_wait() -> None:
    global _throttle_last_request
    interval = _throttle_min_interval_sec
    if interval <= 0:
        return
    with _throttle_lock:
        now = time.monotonic()
        elapsed = now - _throttle_last_request
        if elapsed < interval:
            time.sleep(interval - elapsed)
        _throttle_last_request = time.monotonic()


def _retry_wait_seconds(attempt: int, resp: requests.Response | None) -> float:
    if resp is not None and resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), NHL_GAMELOG_429_BACKOFF_CAP_SEC)
            except ValueError:
                pass
        return min(
            NHL_GAMELOG_BASE_DELAY_SEC * (2 ** max(0, attempt - 1)),
            NHL_GAMELOG_429_BACKOFF_CAP_SEC,
        )
    return NHL_GAMELOG_BASE_DELAY_SEC * attempt


def _season_id(end_year: int) -> str:
    return f"{end_year - 1}{end_year}"


def _val(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return default


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _goalie_saves(g: dict[str, Any]) -> float:
    """NHL game-log API exposes SA/GA; ``saves`` is often omitted."""
    raw = _val(g, "saves", default=None)
    if raw is not None:
        return _to_float(raw)
    sa = _to_float(_val(g, "shotsAgainst", "shots_against", "saveShotsAgainst", default=0))
    ga = _to_float(_val(g, "goalsAgainst", "goals_against", default=0))
    if sa > 0:
        return max(0.0, sa - ga)
    return 0.0


def _goalie_win(g: dict[str, Any]) -> float:
    decision = str(_val(g, "decision", "gameResult", "gameOutcome", default="")).strip().upper()
    if decision in {"W", "WIN", "O"}:
        return 1.0
    if _val(g, "wins", "win", default=None) in (1, 1.0, True, "1"):
        return 1.0
    return 0.0


def _goalie_shutout(g: dict[str, Any], goals_against: float, saves: float) -> float:
    raw = _val(g, "shutout", "shutouts", "so", default=None)
    if raw in (True, 1, 1.0, "1"):
        return 1.0
    if goals_against == 0 and saves > 0:
        return 1.0
    return 0.0


def _games_to_frame(
    player_id: str,
    player_name: str,
    end_year: int,
    games: list[dict[str, Any]],
    *,
    is_goalie: bool,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    log_type = NHL_LOG_GOALIE if is_goalie else NHL_LOG_SKATER
    for g in games:
        if not isinstance(g, dict):
            continue
        base = {
            "player_id": str(player_id),
            "player_name": str(player_name),
            "season": int(end_year),
            "game_id": str(_val(g, "gameId", "game_id", "id", default="")),
            "log_type": log_type,
            "game_date": _val(g, "gameDate", "game_date"),
            "team": str(_val(g, "teamAbbrev", "team", default="UNK")),
            "opponent": str(_val(g, "opponentAbbrev", "opponent", default="UNK")),
        }
        if not base["game_id"]:
            continue
        if is_goalie:
            ga = _to_float(_val(g, "goalsAgainst", "goals_against", default=0))
            saves = _goalie_saves(g)
            row = dict(base)
            row.update(
                {
                    "goals": None,
                    "assists": None,
                    "points": None,
                    "shots": None,
                    "wins": _goalie_win(g),
                    "saves": saves,
                    "goals_against": ga,
                    "shutouts": _goalie_shutout(g, ga, saves),
                }
            )
        else:
            row = dict(base)
            row.update(
                {
                    "goals": _to_float(_val(g, "goals", default=0)),
                    "assists": _to_float(_val(g, "assists", default=0)),
                    "points": _to_float(_val(g, "points", default=0)),
                    "shots": _to_float(_val(g, "shots", "shotsOnGoal", default=0)),
                    "wins": None,
                    "saves": None,
                    "goals_against": None,
                    "shutouts": None,
                }
            )
        rows.append(row)

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["game_date"] = pd.to_datetime(out["game_date"], errors="coerce").dt.date
    out = order_game_log_by_date(out)
    if is_goalie:
        for c in ("wins", "saves", "goals_against", "shutouts"):
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
        out["fantasy_points_espn"] = compute_goalie_fp(out)
    else:
        for c in ("goals", "assists", "points", "shots"):
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
        out["fantasy_points_espn"] = compute_skater_fp(out)
    for col in NHL_PLAYER_GAME_COLUMNS:
        if col not in out.columns:
            out[col] = None
    return out[list(NHL_PLAYER_GAME_COLUMNS)]


def fetch_player_gamelog(
    player_id: str,
    player_name: str,
    end_year: int,
    *,
    is_goalie: bool = False,
) -> pd.DataFrame:
    season_id = _season_id(end_year)
    url = f"https://api-web.nhle.com/v1/player/{player_id}/game-log/{season_id}/2"
    last: Exception | None = None
    payload: dict[str, Any] | None = None
    for attempt in range(1, NHL_GAMELOG_RETRIES + 1):
        _throttle_wait()
        resp: requests.Response | None = None
        try:
            resp = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "fantasy-tracker/1.0 (gamelog-ingest)"},
            )
            if resp.status_code == 429:
                wait = _retry_wait_seconds(attempt, resp)
                print(
                    f"  NHL gamelog {player_id} rate limited (429); "
                    f"waiting {wait:.1f}s ({attempt}/{NHL_GAMELOG_RETRIES})..."
                )
                time.sleep(wait)
                continue
            resp.raise_for_status()
            payload = resp.json()
            break
        except requests.HTTPError as exc:
            last = exc
            if attempt >= NHL_GAMELOG_RETRIES:
                raise
            wait = _retry_wait_seconds(attempt, resp)
            print(f"  NHL gamelog {player_id} failed ({exc}); retrying in {wait:.1f}s...")
            time.sleep(wait)
        except Exception as exc:
            last = exc
            if attempt >= NHL_GAMELOG_RETRIES:
                raise
            wait = _retry_wait_seconds(attempt, resp)
            print(f"  NHL gamelog {player_id} failed ({exc}); retrying in {wait:.1f}s...")
            time.sleep(wait)
    else:
        if last is not None:
            raise last
        return pd.DataFrame()
    if payload is None:
        return pd.DataFrame()
    games = payload.get("gameLog") or payload.get("games") or []
    if not isinstance(games, list) or not games:
        return pd.DataFrame()
    games = filter_nhl_gamelog_games(games)
    if not games:
        return pd.DataFrame()
    return _games_to_frame(
        player_id, player_name, end_year, games, is_goalie=is_goalie
    )


def ingest_season_gamelogs(
    conn,
    end_year: int,
    *,
    limit_players: int | None = None,
    delay_sec: float = NHL_GAMELOG_DEFAULT_DELAY_SEC,
    workers: int = NHL_GAMELOG_DEFAULT_WORKERS,
    use_cache: bool = True,
    refresh_cache: bool = False,
) -> dict[str, int]:
    """Ingest NHL skater and goalie game logs for one season."""
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

    from src.sports.gamelog_bulk import bulk_replace_season_gamelogs, fetch_players_parallel

    configure_nhl_gamelog_throttle(delay_sec)

    by_player: dict[str, dict[str, Any]] = {}
    for _, row in players.iterrows():
        pid = str(row["player_id"]).strip()
        if not pid or pid.lower() in {"nan", "none", "<na>"}:
            continue
        pos = str(row.get("position") or "").strip()
        entry = by_player.get(pid)
        if entry is None:
            entry = {
                "player_name": str(row.get("player_name") or "").strip(),
                "is_goalie": False,
            }
            by_player[pid] = entry
        if is_goalie_position(pos):
            entry["is_goalie"] = True

    tasks: list[dict[str, Any]] = [
        {
            "player_id": pid,
            "player_name": str(meta.get("player_name") or ""),
            "is_goalie": bool(meta.get("is_goalie")),
        }
        for pid, meta in sorted(by_player.items())
    ]
    skipped = len(players) - len(tasks)

    def _fetch(task: dict[str, Any]) -> pd.DataFrame:
        return fetch_player_gamelog(
            str(task["player_id"]),
            str(task.get("player_name") or ""),
            end_year,
            is_goalie=bool(task.get("is_goalie")),
        )

    n_goalies = sum(1 for t in tasks if t.get("is_goalie"))
    n_skaters = len(tasks) - n_goalies
    print(
        f"  NHL gamelog: {n_skaters} skaters, {n_goalies} goalies "
        f"({len(tasks)} players), {workers} workers "
        f"(cache={'on' if use_cache else 'off'})..."
    )
    frames, loaded, failed = fetch_players_parallel(
        tasks,
        _fetch,
        sport_id="nhl",
        season=end_year,
        workers=workers,
        use_cache=use_cache,
        refresh_cache=refresh_cache,
        table_columns=NHL_PLAYER_GAME_COLUMNS,
    )
    skipped += failed
    total = bulk_replace_season_gamelogs(
        conn,
        "nhl_player_game_stats",
        end_year,
        frames,
        columns=NHL_PLAYER_GAME_COLUMNS,
    )
    return {
        "rows": int(total),
        "players_total": int(len(players)),
        "players_loaded": int(loaded),
        "players_skipped": int(skipped),
    }
