#!/usr/bin/env python3
"""Benchmark candidate position/game-log data sources by sport."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.sports.mlb.position_lookup import load_field_position_map  # noqa: E402
from src.sports.mlb.positions import is_pitcher_position  # noqa: E402
from src.sports.nba.positions import normalize_nba_position  # noqa: E402
from src.sports.nba.player_positions import (  # noqa: E402
    _positions_from_player_index,
    _positions_from_team_rosters,
)


@dataclass
class ProbeResult:
    name: str
    metric: str
    elapsed_sec: float
    successes: int
    failures: int
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "metric": self.metric,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "successes": self.successes,
            "failures": self.failures,
            "notes": self.notes,
        }


def _season_str(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _load_players(conn, sport: str, season: int, limit_players: int | None) -> pd.DataFrame:
    table = f"{sport}_player_season_stats"
    q = f"""
        SELECT DISTINCT player_id, player_name, position
        FROM {table}
        WHERE season = ?
        ORDER BY player_id
    """
    params: list[Any] = [int(season)]
    if limit_players:
        q += " LIMIT ?"
        params.append(int(limit_players))
    return conn.execute(q, params).df()


def _probe(name: str, metric: str, fn: Callable[[], tuple[int, int, str]]) -> ProbeResult:
    t0 = time.perf_counter()
    successes, failures, notes = fn()
    return ProbeResult(
        name=name,
        metric=metric,
        elapsed_sec=time.perf_counter() - t0,
        successes=successes,
        failures=failures,
        notes=notes,
    )


def _bakeoff_nba(season: int, limit_players: int | None) -> list[ProbeResult]:
    from nba_api.stats.endpoints import leaguedashplayerstats, playergamelog, playergamelogs

    results: list[ProbeResult] = []
    conn = get_connection(read_only=True)
    try:
        players = _load_players(conn, "nba", season, limit_players)
    finally:
        conn.close()
    if players.empty:
        return [ProbeResult("nba/no-data", "players", 0.0, 0, 1, f"no players for {season}")]

    pids = [str(v).strip() for v in players["player_id"].tolist() if str(v).strip()]
    season_label = _season_str(season)

    results.append(
        _probe(
            "nba-position/playerindex",
            "position-ids",
            lambda: (
                len(_positions_from_player_index(season_label)),
                0,
                "single API request",
            ),
        )
    )
    results.append(
        _probe(
            "nba-position/teamrosters",
            "position-ids",
            lambda: (
                len(_positions_from_team_rosters(season_label)),
                0,
                "multi-team API requests",
            ),
        )
    )
    def league_dash_position_probe() -> tuple[int, int, str]:
        try:
            resp = leaguedashplayerstats.LeagueDashPlayerStats(
                season=season_label,
                season_type_all_star="Regular Season",
                per_mode_detailed="PerGame",
            )
            df = resp.get_data_frames()[0]
            if df.empty:
                return 0, len(pids), "empty response"
            pos_col = "PLAYER_POSITION" if "PLAYER_POSITION" in df.columns else None
            if not pos_col:
                return 0, len(pids), "no PLAYER_POSITION column"
            pid_col = "PLAYER_ID" if "PLAYER_ID" in df.columns else None
            if not pid_col:
                return 0, len(pids), "no PLAYER_ID column"
            pos_map = {}
            for _, row in df.iterrows():
                pid = str(row[pid_col]).strip()
                norm = normalize_nba_position(row[pos_col])
                if pid and norm:
                    pos_map[pid] = norm
            covered = sum(1 for p in pids if p in pos_map)
            return covered, max(0, len(pids) - covered), f"rows={len(df)}"
        except Exception as exc:
            return 0, len(pids), f"error={exc}"

    results.append(
        _probe(
            "nba-position/leaguedash-player-position",
            "sample-players-covered",
            league_dash_position_probe,
        )
    )

    def per_player_probe() -> tuple[int, int, str]:
        ok, fail = 0, 0
        for pid in pids:
            try:
                resp = playergamelog.PlayerGameLog(
                    player_id=pid, season=season_label, season_type_all_star="Regular Season"
                )
                df = resp.get_data_frames()[0]
                if not df.empty:
                    ok += 1
                else:
                    fail += 1
                time.sleep(0.2)
            except Exception:
                fail += 1
        return ok, fail, f"sampled={len(pids)} players"

    results.append(_probe("nba-gamelog/playergamelog", "players-with-rows", per_player_probe))

    def bulk_probe() -> tuple[int, int, str]:
        try:
            resp = playergamelogs.PlayerGameLogs(
                season_nullable=season_label,
                season_type_nullable="Regular Season",
            )
            df = resp.get_data_frames()[0]
            if df.empty:
                return 0, 1, "bulk endpoint returned empty"
            pid_col = "PLAYER_ID" if "PLAYER_ID" in df.columns else "Player_ID"
            have = set(df[pid_col].astype(str).tolist())
            covered = sum(1 for p in pids if p in have)
            return covered, max(0, len(pids) - covered), f"rows={len(df)}"
        except Exception as exc:
            return 0, len(pids), f"error={exc}"

    results.append(_probe("nba-gamelog/playergamelogs", "players-covered", bulk_probe))
    return results


def _bakeoff_mlb(season: int, limit_players: int | None) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    conn = get_connection(read_only=True)
    try:
        players = _load_players(conn, "mlb", season, limit_players)
    finally:
        conn.close()
    if players.empty:
        return [ProbeResult("mlb/no-data", "players", 0.0, 0, 1, f"no players for {season}")]

    pids = [str(v).strip() for v in players["player_id"].tolist() if str(v).strip().isdigit()]
    names = [str(v).strip() for v in players["player_name"].tolist()]
    name_keys = {n.lower() for n in names if n}

    def bref_fg_probe() -> tuple[int, int, str]:
        mapped = load_field_position_map(season)
        covered = len({k for k in mapped.keys() if k in name_keys})
        return covered, max(0, len(name_keys) - covered), "name-based matching"

    results.append(_probe("mlb-position/bref+fg-name-map", "name-coverage", bref_fg_probe))

    def statsapi_people_probe() -> tuple[int, int, str]:
        try:
            url = "https://statsapi.mlb.com/api/v1/sports/1/players"
            resp = requests.get(url, params={"season": season}, timeout=45)
            resp.raise_for_status()
            payload = resp.json()
            people = payload.get("people") or []
            if not isinstance(people, list):
                return 0, len(pids), "bad payload"
            pos_map = {
                str(p.get("id")): str(((p.get("primaryPosition") or {}).get("abbreviation")) or "")
                for p in people
            }
            covered = sum(1 for pid in pids if pos_map.get(pid))
            return covered, max(0, len(pids) - covered), f"people={len(people)}"
        except Exception as exc:
            return 0, len(pids), f"error={exc}"

    results.append(_probe("mlb-position/statsapi-people", "id-coverage", statsapi_people_probe))

    pitcher_by_pid = {
        str(row["player_id"]).strip(): is_pitcher_position(str(row.get("position") or ""))
        for _, row in players.iterrows()
    }

    def gamelog_probe() -> tuple[int, int, str]:
        ok, fail = 0, 0
        for pid in pids:
            try:
                group = "pitching" if pitcher_by_pid.get(pid, False) else "hitting"
                resp = requests.get(
                    f"https://statsapi.mlb.com/api/v1/people/{pid}/stats",
                    params={"stats": "gameLog", "group": group, "season": season},
                    timeout=30,
                )
                resp.raise_for_status()
                rows = ((resp.json().get("stats") or [{}])[0].get("splits") or [])
                if rows:
                    ok += 1
                else:
                    fail += 1
                time.sleep(0.15)
            except Exception:
                fail += 1
        return ok, fail, f"sampled={len(pids)} numeric-player-ids"

    results.append(_probe("mlb-gamelog/statsapi-person", "players-with-rows", gamelog_probe))
    return results


def _bakeoff_nhl(season: int, limit_players: int | None) -> list[ProbeResult]:
    from nhlpy import NHLClient

    results: list[ProbeResult] = []
    conn = get_connection(read_only=True)
    try:
        players = _load_players(conn, "nhl", season, limit_players)
    finally:
        conn.close()
    if players.empty:
        return [ProbeResult("nhl/no-data", "players", 0.0, 0, 1, f"no players for {season}")]

    pids = [str(v).strip() for v in players["player_id"].tolist() if str(v).strip()]
    season_id = f"{season - 1}{season}"
    client = NHLClient()

    def web_probe() -> tuple[int, int, str]:
        ok, fail = 0, 0
        for pid in pids:
            try:
                resp = requests.get(
                    f"https://api-web.nhle.com/v1/player/{pid}/game-log/{season_id}/2",
                    timeout=30,
                )
                resp.raise_for_status()
                payload = resp.json()
                games = payload.get("gameLog") or payload.get("games") or []
                if games:
                    ok += 1
                else:
                    fail += 1
                time.sleep(0.15)
            except Exception:
                fail += 1
        return ok, fail, f"sampled={len(pids)} players"

    results.append(_probe("nhl-gamelog/api-web", "players-with-rows", web_probe))

    def nhlpy_probe() -> tuple[int, int, str]:
        ok, fail = 0, 0
        for pid in pids:
            try:
                rows = client.stats.player_game_log(player_id=pid, season_id=season_id, game_type=2)
                if rows:
                    ok += 1
                else:
                    fail += 1
                time.sleep(0.15)
            except Exception:
                fail += 1
        return ok, fail, f"sampled={len(pids)} players"

    results.append(_probe("nhl-gamelog/nhlpy-wrapper", "players-with-rows", nhlpy_probe))
    return results


def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark candidate sports data sources")
    p.add_argument("--sport", choices=("nba", "mlb", "nhl"), required=True)
    p.add_argument("--season", type=int, required=True, help="Season end year")
    p.add_argument("--limit-players", type=int, default=30, help="Sample size from season table")
    p.add_argument(
        "--output-json",
        type=str,
        default="data/source_bakeoff_latest.json",
        help="Where to write machine-readable results",
    )
    args = p.parse_args()

    init_schema()
    if args.sport == "nba":
        rows = _bakeoff_nba(args.season, args.limit_players)
    elif args.sport == "mlb":
        rows = _bakeoff_mlb(args.season, args.limit_players)
    else:
        rows = _bakeoff_nhl(args.season, args.limit_players)

    payload = {
        "sport": args.sport,
        "season": int(args.season),
        "limit_players": int(args.limit_players) if args.limit_players else None,
        "results": [r.as_dict() for r in rows],
    }
    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Source bakeoff: sport={args.sport} season={args.season}")
    for r in rows:
        print(
            f"- {r.name}: {r.metric}={r.successes} ok, "
            f"failures={r.failures}, {r.elapsed_sec:.2f}s"
            + (f" ({r.notes})" if r.notes else "")
        )
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
