#!/usr/bin/env python3
"""Print season volume distributions for threshold tuning (CLI)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analytics.volume_report import build_volume_summary_table  # noqa: E402
from src.db.connection import db_exists, get_connection  # noqa: E402
from src.settings import get_min_games_default  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Volume gate cross-check for one season")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--min-games", type=int, default=None)
    args = parser.parse_args()

    if not db_exists():
        print("No database found. Run ingest first.")
        sys.exit(1)

    min_games = args.min_games if args.min_games is not None else get_min_games_default()
    conn = get_connection(read_only=True)
    summary = build_volume_summary_table(conn, args.season, min_games=min_games)
    conn.close()

    if summary.empty:
        print(f"No rows for season {args.season} (min games {min_games})")
        sys.exit(1)

    print(f"\nVolume summary — season {args.season}, min games {min_games}\n")
    print(
        summary.to_string(
            index=False,
            columns=[
                "position",
                "metric",
                "threshold",
                "n_players",
                "n_qualified",
                "pct_qualified",
                "p25",
                "median",
                "p75",
            ],
        )
    )


if __name__ == "__main__":
    main()
