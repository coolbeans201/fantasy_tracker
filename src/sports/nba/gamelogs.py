"""Fetch and store NBA player game logs."""

from __future__ import annotations

import re
import time

import pandas as pd

from src.sports.nba.scoring import compute_fp


def _parse_opponent(matchup: str | None) -> str | None:
    if not matchup:
        return None
    text = str(matchup).strip().upper()
    m = re.search(r"(?:@|VS\.?)\s*([A-Z]{2,4})", text)
    return m.group(1) if m else None


def fetch_player_gamelog(player_id: str, end_year: int) -> pd.DataFrame:
    from nba_api.stats.endpoints import playergamelog

    season = f"{end_year - 1}-{str(end_year)[-2:]}"
    resp = playergamelog.PlayerGameLog(
        player_id=str(player_id),
        season=season,
        season_type_all_star="Regular Season",
    )
    time.sleep(0.6)
    raw = resp.get_data_frames()[0]
    if raw.empty:
        return pd.DataFrame()
    out = pd.DataFrame()
    out["player_id"] = str(player_id)
    out["player_name"] = raw.get("PLAYER_NAME", pd.Series([None] * len(raw)))
    out["season"] = end_year
    out["game_id"] = raw["Game_ID"].astype(str)
    out["game_date"] = pd.to_datetime(raw["GAME_DATE"], errors="coerce").dt.date
    out["game_index"] = range(1, len(out) + 1)
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
    return out


def ingest_season_gamelogs(conn, end_year: int, *, limit_players: int | None = None) -> int:
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
        return 0
    conn.execute("DELETE FROM nba_player_game_stats WHERE season = ?", [end_year])
    total = 0
    for _, row in players.iterrows():
        pid = str(row["player_id"])
        try:
            frame = fetch_player_gamelog(pid, end_year)
        except Exception:
            continue
        if frame.empty:
            continue
        if "player_name" not in frame.columns or frame["player_name"].isna().all():
            frame["player_name"] = row.get("player_name")
        conn.register("_nba_games", frame)
        conn.execute("INSERT INTO nba_player_game_stats SELECT * FROM _nba_games")
        conn.unregister("_nba_games")
        total += len(frame)
    return total
