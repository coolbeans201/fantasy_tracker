#!/usr/bin/env python3
"""Ingest NHL regular-season skater + goalie stats via nhl-api-py."""

from __future__ import annotations

import argparse
import inspect
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.db.sport_schema import NHL_PLAYER_SEASON_COLUMNS  # noqa: E402
from src.sports.nhl.positions import (  # noqa: E402
    GOALIE_POSITION,
    SKATER_POSITION,
    is_goalie_position,
    normalize_nhl_skater_position,
)
from src.sports.nhl.scoring import compute_goalie_fp, compute_skater_fp  # noqa: E402

# NHL.com stats API hard-caps each response at 100 rows (see response "total").
NHL_STATS_PAGE_SIZE = 100

_SKATER_SORT = json.dumps(
    [
        {"property": "points", "direction": "DESC"},
        {"property": "gamesPlayed", "direction": "ASC"},
        {"property": "playerId", "direction": "ASC"},
    ]
)


def _season_id(end_year: int) -> str:
    return f"{end_year - 1}{end_year}"


def _col(raw: pd.DataFrame, *names: str, default: str | float = 0) -> pd.Series:
    """First matching column, or a constant series (DataFrame.get defaults are scalars)."""
    for name in names:
        if name in raw.columns:
            return raw[name]
    return pd.Series([default] * len(raw), index=raw.index)


def _num(raw: pd.DataFrame, *names: str) -> pd.Series:
    return pd.to_numeric(_col(raw, *names, default=0), errors="coerce").fillna(0)


def _fetch_stat_pages(client, method: str, season_id: str) -> list:
    """Fetch all regular-season rows; nhlpy drops response total and caps pages at 100."""
    fn = getattr(client.stats, method)
    params = inspect.signature(fn).parameters
    if "season_id" in params and "start_season" not in params:
        legacy = fn(season_id=season_id, game_type_id=2)
        return list(legacy or [])

    from nhlpy.api.query.filters import _goalie_stats_sorts
    from nhlpy.http_client import Endpoint

    if method == "skater_stats_summary":
        resource = "en/skater/summary"
        sort_expr = _SKATER_SORT
        fact_cayenne = "gamesPlayed>=1"
    elif method == "goalie_stats_summary":
        resource = "en/goalie/summary"
        sort_expr = json.dumps(_goalie_stats_sorts(report="summary"))
        fact_cayenne = None
    else:
        raise ValueError(f"Unknown NHL stats method: {method}")

    cayenne = f"gameTypeId=2 and seasonId<={season_id} and seasonId>={season_id}"
    offset = 0
    rows: list = []
    total: int | None = None

    while True:
        query: dict = {
            "isAggregate": False,
            "isGame": False,
            "start": offset,
            "limit": NHL_STATS_PAGE_SIZE,
            "sort": sort_expr,
            "cayenneExp": cayenne,
        }
        if fact_cayenne:
            query["factCayenneExp"] = fact_cayenne

        payload = client.stats.client.get(
            endpoint=Endpoint.API_STATS,
            resource=resource,
            query_params=query,
        ).json()
        batch = payload.get("data") or []
        if total is None:
            total = int(payload.get("total") or 0)

        rows.extend(batch)
        offset += len(batch)
        if not batch:
            break
        if total and offset >= total:
            break
        time.sleep(0.25)

    return rows


def fetch_season(end_year: int) -> pd.DataFrame:
    from nhlpy import NHLClient

    client = NHLClient()
    sid = _season_id(end_year)
    skaters = _fetch_stat_pages(client, "skater_stats_summary", sid)
    goalies = _fetch_stat_pages(client, "goalie_stats_summary", sid)
    frames = []
    if skaters is not None and len(skaters) > 0:
        s = pd.DataFrame(skaters)
        out = pd.DataFrame()
        out["player_id"] = _col(s, "playerId", "player_id").astype(str)
        out["player_name"] = _col(
            s, "skaterFullName", "playerName", "name", default=""
        ).astype(str)
        out["season"] = end_year
        pos_raw = _col(s, "positionCode", "position", default="")
        out["position"] = pos_raw.map(normalize_nhl_skater_position)
        out.loc[out["position"].isna(), "position"] = "F"
        out.loc[out["position"].map(is_goalie_position), "position"] = "F"
        out["team"] = _col(s, "teamAbbrevs", "teamAbbrev", default="UNK").astype(str)
        out["games"] = _num(s, "gamesPlayed", "gp")
        out["goals"] = _num(s, "goals")
        out["assists"] = _num(s, "assists")
        out["points"] = _num(s, "points")
        out["plus_minus"] = _num(s, "plusMinus", "plus_minus")
        out["shots"] = _num(s, "shots")
        out["hits"] = _num(s, "hits")
        out["blocks"] = _num(s, "blockedShots", "blocks")
        for c in ("wins", "saves", "goals_against", "shutouts"):
            out[c] = 0.0
        out["fantasy_points_espn"] = compute_skater_fp(out)
        frames.append(out)
    if goalies is not None and len(goalies) > 0:
        g = pd.DataFrame(goalies)
        out = pd.DataFrame()
        out["player_id"] = _col(g, "playerId", "player_id").astype(str)
        out["player_name"] = _col(
            g, "goalieFullName", "playerName", "name", default=""
        ).astype(str)
        out["season"] = end_year
        out["position"] = GOALIE_POSITION
        out["team"] = _col(g, "teamAbbrevs", "teamAbbrev", default="UNK").astype(str)
        out["games"] = _num(g, "gamesPlayed", "gp")
        out["wins"] = _num(g, "wins")
        out["saves"] = _num(g, "saves")
        out["goals_against"] = _num(g, "goalsAgainst", "goals_against")
        out["shutouts"] = _num(g, "shutouts")
        for c in ("goals", "assists", "points", "plus_minus", "shots", "hits", "blocks"):
            out[c] = 0.0
        out["fantasy_points_espn"] = compute_goalie_fp(out)
        frames.append(out)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)[list(NHL_PLAYER_SEASON_COLUMNS)]


def ingest_season(end_year: int) -> None:
    init_schema()
    conn = get_connection()
    frame = fetch_season(end_year)
    if frame.empty:
        print(f"No NHL data for season ending {end_year}.")
        conn.close()
        return
    conn.execute("DELETE FROM nhl_player_season_stats WHERE season = ?", [end_year])
    frame = frame[list(NHL_PLAYER_SEASON_COLUMNS)]
    conn.register("_nhl", frame)
    cols = ", ".join(NHL_PLAYER_SEASON_COLUMNS)
    conn.execute(f"INSERT INTO nhl_player_season_stats ({cols}) SELECT {cols} FROM _nhl")
    conn.unregister("_nhl")
    conn.execute("DELETE FROM nhl_ingest_manifest WHERE season = ?", [end_year])
    conn.execute(
        """
        INSERT INTO nhl_ingest_manifest (season, ingested_at, row_count)
        VALUES (?, ?, ?)
        """,
        [end_year, datetime.now(timezone.utc), len(frame)],
    )
    conn.close()
    goalies = int(frame["position"].map(is_goalie_position).sum())
    skaters = len(frame) - goalies
    print(
        f"Ingested NHL season {end_year}: {len(frame)} rows "
        f"({skaters} skaters, {goalies} goalies)"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest NHL season stats into DuckDB")
    p.add_argument(
        "--season",
        type=int,
        help="Season end year (e.g. 2025 = 2024–25); not used with --bulk",
    )
    p.add_argument("--bulk", action="store_true", help="Ingest --from-year through --to-year")
    p.add_argument("--from-year", type=int, default=2005, help="First season end year (bulk)")
    p.add_argument("--to-year", type=int, default=2025, help="Last season end year (bulk)")
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop bulk ingest on first error (default: skip and continue)",
    )
    args = p.parse_args()

    if args.bulk:
        years = range(args.from_year, args.to_year + 1)
        print(
            f"Bulk NHL ingest: {args.from_year}–{args.to_year} "
            f"({len(years)} seasons, end-year keys)"
        )
        skipped: list[int] = []
        for end_year in years:
            print(f"--- NHL {end_year} ({_season_id(end_year)}) ---")
            try:
                ingest_season(end_year)
            except Exception as exc:
                if args.fail_fast:
                    raise
                print(f"  WARNING: skipped NHL {end_year}: {exc}")
                skipped.append(end_year)
            time.sleep(1.0)
        if skipped:
            print(f"Skipped {len(skipped)} season(s): {skipped}")
            print("Re-run failed years, e.g. --season 2024")
    elif args.season is not None:
        ingest_season(args.season)
    else:
        p.error("Provide --season YEAR or --bulk with --from-year and --to-year")


if __name__ == "__main__":
    main()
