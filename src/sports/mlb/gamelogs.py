"""Fetch and store MLB player game logs."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

from src.db.sport_schema import MLB_PLAYER_GAME_COLUMNS
from src.sports.game_logs import order_game_log_by_date
from src.sports.mlb.positions import is_pitcher_position
from src.sports.mlb.scoring import compute_hitter_fp, compute_pitcher_fp
from src.sports.season_type import MLB_REGULAR_GAME_TYPE, is_mlb_regular_season_split

_LOG_HITTING = "hitting"
_LOG_PITCHING = "pitching"

_MLB_STATS_URL = "https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
MLB_GAMELOG_RETRIES = 4
MLB_GAMELOG_BASE_DELAY_SEC = 1.0


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


_MLB_NUMERIC_COLUMNS = (
    "season",
    "game_index",
    "runs",
    "home_runs",
    "rbi",
    "stolen_bases",
    "walks",
    "strikeouts_bat",
    "wins",
    "strikeouts_pitch",
    "saves",
    "innings_pitched",
    "era",
    "fantasy_points_espn",
)


def _coerce_mlb_gamelog_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize dtypes so hitting + pitching frames concat without pandas warnings."""
    if frame.empty:
        return frame
    out = frame.copy()
    out.columns = [str(c).lower() for c in out.columns]
    for col in MLB_PLAYER_GAME_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    out = out[list(MLB_PLAYER_GAME_COLUMNS)]
    for col in _MLB_NUMERIC_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


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
            if not is_mlb_regular_season_split(split):
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
                row["log_type"] = _LOG_PITCHING
                row.update(
                    {
                        "runs": None,
                        "home_runs": None,
                        "rbi": None,
                        "stolen_bases": None,
                        "walks": None,
                        "strikeouts_bat": None,
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
                row["log_type"] = _LOG_HITTING
                row.update(
                    {
                        "runs": _to_float(stat.get("runs")),
                        "home_runs": _to_float(stat.get("homeRuns")),
                        "rbi": _to_float(stat.get("rbi")),
                        "stolen_bases": _to_float(stat.get("stolenBases")),
                        "walks": _to_float(stat.get("baseOnBalls")),
                        "strikeouts_bat": _to_float(stat.get("strikeOuts")),
                        "wins": None,
                        "strikeouts_pitch": None,
                        "saves": None,
                        "innings_pitched": None,
                        "era": None,
                    }
                )
                rows.append(row)

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["game_date"] = pd.to_datetime(out["game_date"], errors="coerce").dt.date
    out = order_game_log_by_date(out)

    hit_mask = out["log_type"] == _LOG_HITTING
    pit_mask = out["log_type"] == _LOG_PITCHING
    out["fantasy_points_espn"] = 0.0
    if hit_mask.any():
        out.loc[hit_mask, "fantasy_points_espn"] = compute_hitter_fp(out.loc[hit_mask])
    if pit_mask.any():
        out.loc[pit_mask, "fantasy_points_espn"] = compute_pitcher_fp(out.loc[pit_mask])

    for col in MLB_PLAYER_GAME_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA
    return _coerce_mlb_gamelog_frame(out)


def fetch_player_gamelog(
    player_id: str, player_name: str, end_year: int, *, is_pitcher: bool
) -> pd.DataFrame:
    params = {
        "stats": "gameLog",
        "group": "pitching" if is_pitcher else "hitting",
        "season": int(end_year),
        "gameType": MLB_REGULAR_GAME_TYPE,
    }
    last: Exception | None = None
    for attempt in range(1, MLB_GAMELOG_RETRIES + 1):
        try:
            resp = requests.get(
                _MLB_STATS_URL.format(player_id=player_id),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
            break
        except Exception as exc:
            last = exc
            if attempt >= MLB_GAMELOG_RETRIES:
                raise
            wait = MLB_GAMELOG_BASE_DELAY_SEC * attempt
            print(f"  MLB gamelog {player_id} failed ({exc}); retrying in {wait:.1f}s...")
            time.sleep(wait)
    else:
        if last is not None:
            raise last
        return pd.DataFrame()
    return _extract_rows(player_id, player_name, end_year, payload)


def fetch_player_gamelog_combined(
    player_id: str,
    player_name: str,
    end_year: int,
    *,
    is_pitcher: bool,
    two_way: bool = False,
) -> pd.DataFrame:
    """Hitting log for all players; pitching log when pitcher / two-way / pitching exists."""
    parts: list[pd.DataFrame] = []
    try:
        hitting = fetch_player_gamelog(
            player_id, player_name, end_year, is_pitcher=False
        )
        if not hitting.empty:
            parts.append(hitting)
    except Exception:
        pass
    try:
        pitching = fetch_player_gamelog(
            player_id, player_name, end_year, is_pitcher=True
        )
        if not pitching.empty:
            parts.append(pitching)
    except Exception:
        pass
    if not parts:
        return pd.DataFrame()
    prepared = [_coerce_mlb_gamelog_frame(part) for part in parts]
    if len(prepared) == 1:
        out = prepared[0]
    else:
        out = pd.concat(prepared, ignore_index=True, sort=False)
    return out.drop_duplicates(
        subset=["player_id", "season", "game_id", "log_type"],
        keep="first",
    )


def ingest_season_gamelogs(
    conn,
    end_year: int,
    *,
    limit_players: int | None = None,
    delay_sec: float = 0.25,
    workers: int = 6,
    use_cache: bool = True,
    refresh_cache: bool = False,
) -> dict[str, int]:
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
        return {"rows": 0, "players_total": 0, "players_loaded": 0, "players_skipped": 0}

    # Players can appear in multiple season rows (team splits / position splits).
    # Build one ingest record per player_id; track pitcher + two-way for game-log pulls.
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
                "is_hitter": False,
            }
            by_player[pid] = entry
        pos = str(row.get("position") or "").strip()
        if is_pitcher_position(pos):
            entry["is_pitcher"] = True
        else:
            entry["is_hitter"] = True

    for entry in by_player.values():
        entry["two_way"] = bool(entry.get("is_pitcher") and entry.get("is_hitter"))

    from src.sports.gamelog_bulk import bulk_replace_season_gamelogs, fetch_players_parallel

    tasks: list[dict[str, Any]] = []
    skipped = 0
    for pid in sorted(by_player):
        if not pid.isdigit():
            skipped += 1
            continue
        meta = by_player[pid]
        tasks.append(
            {
                "player_id": pid,
                "player_name": str(meta.get("player_name") or "").strip(),
                "is_pitcher": bool(meta.get("is_pitcher")),
                "two_way": bool(meta.get("two_way")),
            }
        )

    def _fetch(task: dict[str, Any]) -> pd.DataFrame:
        if delay_sec > 0:
            time.sleep(delay_sec)
        return fetch_player_gamelog_combined(
            str(task["player_id"]),
            str(task.get("player_name") or ""),
            end_year,
            is_pitcher=bool(task.get("is_pitcher")),
            two_way=bool(task.get("two_way")),
        )

    print(
        f"  MLB gamelog: {len(tasks)} players, {workers} workers "
        f"(cache={'on' if use_cache else 'off'})..."
    )
    frames, loaded, failed = fetch_players_parallel(
        tasks,
        _fetch,
        sport_id="mlb",
        season=end_year,
        workers=workers,
        use_cache=use_cache,
        refresh_cache=refresh_cache,
        table_columns=MLB_PLAYER_GAME_COLUMNS,
    )
    skipped += failed
    total = bulk_replace_season_gamelogs(
        conn,
        "mlb_player_game_stats",
        end_year,
        frames,
        columns=MLB_PLAYER_GAME_COLUMNS,
    )
    return {
        "rows": int(total),
        "players_total": int(len(by_player)),
        "players_loaded": int(loaded),
        "players_skipped": int(skipped),
    }
