#!/usr/bin/env python3
"""Ingest MLB player game logs (per-game profile rows)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.sports.mlb.gamelogs import ingest_season_gamelogs  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest MLB player game logs")
    p.add_argument("--season", type=int, required=True, help="Season year (e.g. 2024)")
    p.add_argument(
        "--limit-players",
        type=int,
        default=None,
        help="Optional cap on players for smoke tests.",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="Delay between player requests in seconds.",
    )
    args = p.parse_args()

    init_schema()
    conn = get_connection()
    try:
        rows = ingest_season_gamelogs(
            conn,
            args.season,
            limit_players=args.limit_players,
            delay_sec=max(0.0, float(args.delay)),
        )
        print(f"Ingested MLB game logs for {args.season}: {rows} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
