#!/usr/bin/env python3
"""Print which seasons have FantasyPros draft ECR in DuckDB."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import db_exists, get_connection  # noqa: E402
from src.db.queries import (  # noqa: E402
    list_ingested_seasons,
    list_rankings_seasons,
    rankings_manifest_summary,
)


def main() -> None:
    if not db_exists():
        print("No database. Run ingest_season.py first.")
        return

    conn = get_connection()
    try:
        stats_seasons = list_ingested_seasons(conn)
        rank_seasons = list_rankings_seasons(conn)
        manifest = rankings_manifest_summary(conn)
    finally:
        conn.close()

    print("Stats seasons ingested:", len(stats_seasons))
    if stats_seasons:
        print(f"  {stats_seasons[-1]}–{stats_seasons[0]}")

    if manifest:
        print(
            f"\nRankings ingest: {manifest['draft_rows']} draft rows, "
            f"{manifest['weekly_rows']} weekly rows"
        )
        if manifest.get("ingested_at"):
            print(f"  Last ingest: {manifest['ingested_at']}")

    if not rank_seasons:
        print("\nNo draft ECR seasons in DB. Run: scripts/ingest_rankings.py")
        return

    print(f"\nDraft ECR seasons ({len(rank_seasons)}):")
    print(" ", ", ".join(str(s) for s in rank_seasons))

    missing = sorted(set(stats_seasons) - set(rank_seasons), reverse=True)
    if missing:
        print(f"\nStats seasons WITHOUT draft ECR ({len(missing)}):")
        print(" ", ", ".join(str(s) for s in missing))


if __name__ == "__main__":
    main()
