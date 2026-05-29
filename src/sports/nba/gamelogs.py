"""Fetch and store NBA player game logs."""

from __future__ import annotations

import calendar
import re
import time
from typing import Any

import pandas as pd

from src.sports.game_logs import order_game_log_by_date
from src.sports.nba.scoring import compute_fp
from src.sports.season_type import filter_nba_gamelog_frame

NBA_GAMELOG_RETRIES = 6
NBA_GAMELOG_BASE_DELAY_SEC = 1.5
NBA_GAMELOG_TIMEOUT_SEC = 90
NBA_GAMELOG_CHUNK_SLEEP_SEC = 0.8


def _parse_opponent(matchup: str | None) -> str | None:
    if not matchup:
        return None
    text = str(matchup).strip().upper()
    m = re.search(r"(?:@|VS\.?)\s*([A-Z]{2,4})", text)
    return m.group(1) if m else None


def _season_str(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _month_date_ranges(end_year: int) -> list[tuple[str, str]]:
    """Regular-season months as MM/DD/YYYY for stats.nba.com date filters."""
    ranges: list[tuple[str, str]] = []
    for year, month_start, month_end in (
        (end_year - 1, 10, 12),
        (end_year, 1, 6),
    ):
        for month in range(month_start, month_end + 1):
            last_day = calendar.monthrange(year, month)[1]
            date_from = f"{month:02d}/01/{year}"
            date_to = f"{month:02d}/{last_day}/{year}"
            ranges.append((date_from, date_to))
    return ranges


def _raw_gamelog_to_frame(raw: pd.DataFrame, end_year: int) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=raw.index.copy())
    pid_col = "PLAYER_ID" if "PLAYER_ID" in raw.columns else "Player_ID"
    if pid_col not in raw.columns:
        return pd.DataFrame()
    out["player_id"] = raw[pid_col].astype(str)
    out["player_name"] = raw.get("PLAYER_NAME", pd.Series([None] * len(raw)))
    out["season"] = end_year
    if "GAME_ID" in raw.columns:
        out["game_id"] = raw["GAME_ID"].astype(str)
    else:
        out["game_id"] = raw.get("GAME_ID", pd.Series([None] * len(raw))).astype(str)
    out["game_date"] = pd.to_datetime(raw.get("GAME_DATE"), errors="coerce").dt.date
    out["team"] = raw.get("TEAM_ABBREVIATION", pd.Series(["UNK"] * len(raw))).astype(str)
    out["opponent"] = raw.get("MATCHUP", pd.Series([None] * len(raw))).map(_parse_opponent)
    for src, dst in (
        ("PTS", "points"),
        ("REB", "rebounds"),
        ("AST", "assists"),
        ("STL", "steals"),
        ("BLK", "blocks"),
        ("TOV", "turnovers"),
        ("FG3M", "three_pointers"),
    ):
        if src in raw.columns:
            out[dst] = pd.to_numeric(raw[src], errors="coerce").fillna(0)
        else:
            out[dst] = 0.0
    out["fantasy_points_espn"] = compute_fp(out)
    return order_game_log_by_date(out)


def _fetch_playergamelogs_raw(
    end_year: int,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    timeout_sec: float = NBA_GAMELOG_TIMEOUT_SEC,
) -> pd.DataFrame:
    from nba_api.stats.endpoints import playergamelogs

    season = _season_str(end_year)
    kwargs: dict[str, Any] = {
        "season_nullable": season,
        "season_type_nullable": "Regular Season",
        "league_id_nullable": "00",
        "timeout": int(timeout_sec),
    }
    if date_from and date_to:
        kwargs["date_from_nullable"] = date_from
        kwargs["date_to_nullable"] = date_to

    last: Exception | None = None
    label = f"{date_from}-{date_to}" if date_from else "full-season"
    for attempt in range(1, NBA_GAMELOG_RETRIES + 1):
        try:
            resp = playergamelogs.PlayerGameLogs(**kwargs)
            return filter_nba_gamelog_frame(resp.get_data_frames()[0])
        except Exception as exc:
            last = exc
            if attempt >= NBA_GAMELOG_RETRIES:
                break
            wait = NBA_GAMELOG_BASE_DELAY_SEC * attempt
            print(f"  NBA bulk gamelog ({label}) failed ({exc}); retrying in {wait:.1f}s...")
            time.sleep(wait)
    assert last is not None
    raise last


def fetch_season_gamelogs_bulk(
    end_year: int,
    *,
    timeout_sec: float = NBA_GAMELOG_TIMEOUT_SEC,
    use_monthly_chunks: bool = True,
) -> pd.DataFrame:
    """Fetch season player game logs via PlayerGameLogs (full season, then monthly chunks)."""
    try:
        raw = _fetch_playergamelogs_raw(end_year, timeout_sec=timeout_sec)
        if not raw.empty:
            return _raw_gamelog_to_frame(raw, end_year)
    except Exception as exc:
        print(f"  NBA full-season bulk gamelog failed ({exc})")

    if not use_monthly_chunks:
        return pd.DataFrame()

    print("  NBA bulk gamelog: trying monthly date chunks...")
    parts: list[pd.DataFrame] = []
    for date_from, date_to in _month_date_ranges(end_year):
        try:
            raw = _fetch_playergamelogs_raw(
                end_year,
                date_from=date_from,
                date_to=date_to,
                timeout_sec=timeout_sec,
            )
        except Exception as exc:
            print(f"  NBA chunk {date_from}–{date_to} failed ({exc}); skipping")
            time.sleep(NBA_GAMELOG_CHUNK_SLEEP_SEC)
            continue
        chunk = _raw_gamelog_to_frame(raw, end_year)
        if not chunk.empty:
            parts.append(chunk)
        time.sleep(NBA_GAMELOG_CHUNK_SLEEP_SEC)

    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    out = out.drop_duplicates(subset=["player_id", "season", "game_id"], keep="first")
    return order_game_log_by_date(out)


def fetch_player_gamelog(
    player_id: str,
    end_year: int,
    *,
    timeout_sec: float = NBA_GAMELOG_TIMEOUT_SEC,
) -> pd.DataFrame:
    from nba_api.stats.endpoints import playergamelog

    season = _season_str(end_year)
    last: Exception | None = None
    for attempt in range(1, NBA_GAMELOG_RETRIES + 1):
        try:
            resp = playergamelog.PlayerGameLog(
                player_id=str(player_id),
                season=season,
                season_type_all_star="Regular Season",
                timeout=int(timeout_sec),
            )
            time.sleep(0.6)
            break
        except Exception as exc:
            last = exc
            if attempt >= NBA_GAMELOG_RETRIES:
                raise
            wait = NBA_GAMELOG_BASE_DELAY_SEC * attempt
            print(f"  NBA gamelog {player_id} failed ({exc}); retrying in {wait:.1f}s...")
            time.sleep(wait)
    else:
        if last is not None:
            raise last
        return pd.DataFrame()
    raw = filter_nba_gamelog_frame(resp.get_data_frames()[0])
    if raw.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=raw.index.copy())
    out["player_id"] = str(player_id)
    out["player_name"] = raw.get("PLAYER_NAME", pd.Series([None] * len(raw)))
    out["season"] = end_year
    if "Game_ID" in raw.columns:
        out["game_id"] = raw["Game_ID"].astype(str)
    else:
        out["game_id"] = raw.get("GAME_ID", pd.Series([None] * len(raw))).astype(str)
    out["game_date"] = pd.to_datetime(raw["GAME_DATE"], errors="coerce").dt.date
    out["team"] = raw.get("TEAM_ABBREVIATION", pd.Series(["UNK"] * len(raw))).astype(str)
    out["opponent"] = raw.get("MATCHUP", pd.Series([None] * len(raw))).map(_parse_opponent)
    for src, dst in (
        ("PTS", "points"),
        ("REB", "rebounds"),
        ("AST", "assists"),
        ("STL", "steals"),
        ("BLK", "blocks"),
        ("TOV", "turnovers"),
        ("FG3M", "three_pointers"),
    ):
        if src in raw.columns:
            out[dst] = pd.to_numeric(raw[src], errors="coerce").fillna(0)
        else:
            out[dst] = 0.0
    out["fantasy_points_espn"] = compute_fp(out)
    return order_game_log_by_date(out)


def ingest_season_gamelogs(
    conn,
    end_year: int,
    *,
    limit_players: int | None = None,
    delay_sec: float = 0.6,
    timeout_sec: float = NBA_GAMELOG_TIMEOUT_SEC,
    per_player_only: bool = False,
) -> dict[str, int]:
    """Ingest game logs for all players with season stats (optional limit for tests)."""
    q = """
        SELECT DISTINCT player_id, player_name
        FROM nba_player_season_stats
        WHERE season = ?
        ORDER BY player_id
    """
    params: list = [end_year]
    if limit_players:
        q += " LIMIT ?"
        params.append(int(limit_players))
    players = conn.execute(q, params).df()
    if players.empty:
        return {"rows": 0, "players_total": 0, "players_loaded": 0, "players_skipped": 0}
    conn.execute("DELETE FROM nba_player_game_stats WHERE season = ?", [end_year])
    requested = [str(v).strip() for v in players["player_id"].tolist()]
    requested = [p for p in requested if p and p.lower() not in {"nan", "none", "<na>"}]
    requested_set = set(requested)

    frame = pd.DataFrame()
    if not per_player_only:
        try:
            frame = fetch_season_gamelogs_bulk(end_year, timeout_sec=timeout_sec)
            if frame.empty:
                raise RuntimeError("bulk endpoint returned no rows")
            frame = frame[frame["player_id"].astype(str).isin(requested_set)].copy()
        except Exception as exc:
            print(f"  NBA bulk gamelog unavailable ({exc}); falling back to per-player mode")

    if frame.empty:
        parts: list[pd.DataFrame] = []
        total = len(requested)
        for i, pid in enumerate(requested, start=1):
            try:
                part = fetch_player_gamelog(pid, end_year, timeout_sec=timeout_sec)
            except Exception:
                continue
            if not part.empty:
                parts.append(part)
            if i % 25 == 0 or i == total:
                print(f"  NBA per-player gamelog: {i}/{total} players processed...")
            if delay_sec > 0:
                time.sleep(delay_sec)
        frame = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    if frame.empty:
        return {
            "rows": 0,
            "players_total": int(len(requested_set)),
            "players_loaded": 0,
            "players_skipped": int(len(requested_set)),
        }

    name_map = {
        str(row["player_id"]).strip(): row.get("player_name")
        for _, row in players.iterrows()
    }
    if "player_name" in frame.columns:
        missing_name = frame["player_name"].isna() | frame["player_name"].astype(str).str.strip().eq("")
        frame.loc[missing_name, "player_name"] = frame.loc[missing_name, "player_id"].map(name_map)
    else:
        frame["player_name"] = frame["player_id"].map(name_map)

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
    frame = order_game_log_by_date(frame)
    if frame.empty:
        return {
            "rows": 0,
            "players_total": int(len(requested_set)),
            "players_loaded": 0,
            "players_skipped": int(len(requested_set)),
        }

    conn.register("_nba_games", frame)
    conn.execute("INSERT INTO nba_player_game_stats SELECT * FROM _nba_games")
    conn.unregister("_nba_games")
    loaded_ids = set(frame["player_id"].astype(str).unique().tolist())
    loaded = len(loaded_ids & requested_set)
    total = len(frame)
    skipped = max(0, len(requested_set) - loaded)
    return {
        "rows": int(total),
        "players_total": int(len(requested_set)),
        "players_loaded": int(loaded),
        "players_skipped": int(skipped),
    }
