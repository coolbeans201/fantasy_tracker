#!/usr/bin/env python3
"""Overlay FantasyPros player positions onto ingested NBA/MLB season stats."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.rankings.fantasypros_config import ENV_API_KEY  # noqa: E402
from src.rankings.fantasypros_positions import (  # noqa: E402
    fantasypros_configured,
    refresh_positions_in_database,
)
from src.sports.player_seasons import stats_table  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(
        description="Fix NBA/MLB positions in DuckDB using FantasyPros /players"
    )
    p.add_argument("--sport", choices=["nba", "mlb"], required=True)
    p.add_argument(
        "--season",
        type=int,
        help="Only update this season end-year (default: all ingested seasons)",
    )
    p.add_argument(
        "--refresh-fp-cache",
        action="store_true",
        help="Re-download FantasyPros /players (ignore local cache)",
    )
    args = p.parse_args()

    if not fantasypros_configured():
        print(
            f"Set {ENV_API_KEY} in your environment or project .env file "
            f"(see .env.example)."
        )
        sys.exit(1)

    init_schema()
    conn = get_connection()
    try:
        if args.season is not None:
            seasons = [int(args.season)]
        else:
            table = stats_table(args.sport)
            rows = conn.execute(
                f"SELECT DISTINCT season FROM {table} ORDER BY season"
            ).fetchall()
            seasons = [int(r[0]) for r in rows]

        total_updated = 0
        for i, season in enumerate(seasons):
            summary = refresh_positions_in_database(
                conn,
                args.sport,
                season=season,
                refresh_fp_cache=args.refresh_fp_cache and i == 0,
            )
            print(
                f"{args.sport.upper()} {season}: "
                f"{summary['updated']} position(s) updated "
                f"({summary['rows']} rows checked)"
            )
            total_updated += int(summary["updated"])
        if total_updated == 0 and seasons:
            print(
                "\nNo rows updated. If you saw 403 errors above, run:\n"
                "  .\\.venv\\Scripts\\python.exe scripts\\fantasypros_probe.py"
            )
        else:
            print(f"Done. Total updates: {total_updated}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
