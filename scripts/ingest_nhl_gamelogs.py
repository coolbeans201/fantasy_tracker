#!/usr/bin/env python3
"""Ingest NHL skater game logs (per-game profile rows)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.sports.nhl.gamelogs import ingest_season_gamelogs  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest NHL skater and goalie game logs")
    p.add_argument(
        "--season",
        type=int,
        required=True,
        help="Season end year (e.g. 2025 = 2024-25)",
    )
    p.add_argument(
        "--limit-players",
        type=int,
        default=None,
        help="Optional cap on players for smoke tests.",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.65,
        help="Minimum seconds between NHL API requests (global, all workers).",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Parallel fetch workers (keep low; NHL rate-limits aggressively).",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip data/cache/gamelogs/nhl/{season}/ resume files.",
    )
    p.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Refetch all players even if cache exists.",
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
            workers=max(1, int(args.workers)),
            use_cache=not args.no_cache,
            refresh_cache=args.refresh_cache,
        )
        print(
            f"Ingested NHL game logs for {args.season}: {summary['rows']} rows "
            f"({summary['players_loaded']}/{summary['players_total']} players, "
            f"skipped={summary['players_skipped']})"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
