#!/usr/bin/env python3
"""Ingest NBA player game logs (per-game breakdown for profiles)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.sports.nba.gamelogs import ingest_season_gamelogs  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest NBA player game logs")
    p.add_argument("--season", type=int, required=True, help="Season end year (e.g. 2024)")
    p.add_argument(
        "--limit-players",
        type=int,
        default=None,
        help="Cap players ingested (testing / partial runs)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.6,
        help="Delay between per-player fallback requests (seconds).",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="HTTP timeout for NBA Stats API calls.",
    )
    p.add_argument(
        "--per-player-only",
        action="store_true",
        help="Skip bulk PlayerGameLogs and fetch one player at a time (slower, more reliable).",
    )
    args = p.parse_args()
    init_schema()
    conn = get_connection()
    try:
        summary = ingest_season_gamelogs(
            conn,
            args.season,
            limit_players=args.limit_players,
            delay_sec=max(0.0, float(args.delay)),
            timeout_sec=max(30.0, float(args.timeout)),
            per_player_only=args.per_player_only,
        )
    finally:
        conn.close()
    print(
        f"Ingested {summary['rows']} NBA game log rows for season {args.season} "
        f"({summary['players_loaded']}/{summary['players_total']} players, "
        f"skipped={summary['players_skipped']})"
    )


if __name__ == "__main__":
    main()
