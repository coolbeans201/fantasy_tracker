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
    import argparse

    p = argparse.ArgumentParser(description="Draft ECR coverage vs ingested stats")
    p.add_argument("--sport", choices=["nfl", "mlb", "nba", "nhl"], default="nfl")
    p.add_argument("--season", type=int, default=None)
    args = p.parse_args()

    if not db_exists():
        print("No database. Run ingest_season.py first.")
        return

    conn = get_connection()
    try:
        sid = args.sport.strip().lower()
        if sid == "nfl":
            stats_seasons = list_ingested_seasons(conn)
            rank_seasons = list_rankings_seasons(conn)
        else:
            from src.sports.data_coverage import sport_data_coverage

            cov = sport_data_coverage(conn, sid)
            stats_seasons = list(cov["stats_seasons"])
            rank_seasons = list(cov["draft_ecr_seasons"])
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

    print(f"\nDraft ECR seasons ({len(rank_seasons)}) [{sid.upper()}]:")
    print(" ", ", ".join(str(s) for s in rank_seasons))

    if args.season is not None:
        from src.db.queries import season_has_rankings

        ok = season_has_rankings(conn, args.season, sport=sid if sid != "nfl" else None)
        print(f"\nSeason {args.season} ready for rank Δ UI: {ok}")

    missing_candidates = set(stats_seasons) - set(rank_seasons)
    if sid != "nfl":
        from src.rankings.fantasypros_limits import (
            FP_SPORT_DRAFT_ECR_MIN_SEASON,
            sport_draft_ecr_supported,
        )

        unsupported = [s for s in stats_seasons if not sport_draft_ecr_supported(sid, s)]
        if unsupported:
            print(
                f"\nPre-{FP_SPORT_DRAFT_ECR_MIN_SEASON} stats seasons (FP draft ECR N/A): "
                f"{len(unsupported)}"
            )
            print(" ", ", ".join(str(s) for s in unsupported[:20]))
        missing_candidates = {
            s for s in missing_candidates if sport_draft_ecr_supported(sid, s)
        }

    missing = sorted(missing_candidates, reverse=True)
    if missing:
        print(f"\nStats seasons WITHOUT draft ECR ({len(missing)}):")
        print(" ", ", ".join(str(s) for s in missing))


if __name__ == "__main__":
    main()
