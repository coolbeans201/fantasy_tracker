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
    args = p.parse_args()
    init_schema()
    conn = get_connection()
    try:
        rows = ingest_season_gamelogs(
            conn, args.season, limit_players=args.limit_players
        )
    finally:
        conn.close()
    print(f"Ingested {rows} NBA game log rows for season {args.season}")


if __name__ == "__main__":
    main()
