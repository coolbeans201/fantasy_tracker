#!/usr/bin/env python3
"""Ingest FantasyPros ECR rankings (nflverse) into DuckDB."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.db.queries import list_rankings_seasons  # noqa: E402
from src.rankings.ingest import ingest_rankings_from_nflverse  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Load FantasyPros ECR into DuckDB")
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="Append instead of replacing existing ECR tables",
    )
    args = parser.parse_args()

    init_schema()
    conn = get_connection()
    try:
        summary = ingest_rankings_from_nflverse(conn, replace=not args.no_replace)
    finally:
        conn.close()

    print(
        f"Draft ECR rows: {summary['draft_rows']} "
        f"(unmapped source rows skipped: {summary['draft_unmapped']})"
    )
    print(
        f"Weekly ECR rows: {summary['weekly_rows']} "
        f"(unmapped source rows skipped: {summary['weekly_unmapped']})"
    )
    conn = get_connection()
    try:
        seasons = list_rankings_seasons(conn)
    finally:
        conn.close()
    if seasons:
        span = f"{seasons[0]}–{seasons[-1]}" if len(seasons) > 1 else str(seasons[0])
        print(f"Draft ECR seasons in DB ({len(seasons)}): {span}")
        print("  ", ", ".join(str(s) for s in seasons))
    else:
        print("No draft ECR seasons stored (check source data / player ID mapping).")


if __name__ == "__main__":
    main()
