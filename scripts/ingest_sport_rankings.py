#!/usr/bin/env python3
"""Ingest FantasyPros draft ECR and/or projections for MLB, NBA, or NHL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.rankings.fantasypros_client import FantasyProsAPIError  # noqa: E402
from src.rankings.fantasypros_config import ENV_API_KEY  # noqa: E402
from src.rankings.sport_ingest import (  # noqa: E402
    ingest_sport_draft_ecr,
    ingest_sport_projections,
)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Ingest FantasyPros rankings/projections for a sport season"
    )
    p.add_argument("--sport", choices=["nba", "mlb", "nhl"], required=True)
    p.add_argument("--season", type=int, required=True)
    p.add_argument(
        "--draft-only",
        action="store_true",
        help="Only load draft ECR into ecr_draft",
    )
    p.add_argument(
        "--projections-only",
        action="store_true",
        help="Only load projections into fp_projections",
    )
    p.add_argument(
        "--projection-type",
        default="preseason",
        help="Projection type param (preseason, ros, weekly, daily for MLB)",
    )
    p.add_argument(
        "--no-replace",
        action="store_true",
        help="Append rows instead of replacing sport+season (and type for projections)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between consensus/projection API calls (rate limiting)",
    )
    p.add_argument(
        "--refresh-fp",
        action="store_true",
        help="Re-download FantasyPros /players (ignore local cache)",
    )
    args = p.parse_args()

    if args.draft_only and args.projections_only:
        p.error("Use at most one of --draft-only and --projections-only")

    init_schema()
    conn = get_connection()
    replace = not args.no_replace
    summaries: list[dict] = []

    try:
        if not args.projections_only:
            summaries.append(
                ingest_sport_draft_ecr(
                    conn,
                    args.sport,
                    args.season,
                    replace=replace,
                    delay_sec=args.delay,
                    refresh_fp_cache=args.refresh_fp,
                )
            )
        if not args.draft_only:
            summaries.append(
                ingest_sport_projections(
                    conn,
                    args.sport,
                    args.season,
                    projection_type=args.projection_type,
                    replace=replace,
                    delay_sec=args.delay,
                )
            )
    except FantasyProsAPIError as exc:
        print(exc)
        if "429" in str(exc):
            print(
                "FantasyPros rate limit — wait 60s and retry with a slower pace, e.g. "
                f"--delay 2 (current {args.delay})."
            )
            if args.sport in ("mlb", "nhl") and not args.refresh_fp:
                print(
                    "MLB/NHL draft can use cached data/cache/fantasypros/"
                    f"{args.sport}_players.json if you have it from a prior run."
                )
        sys.exit(1)
    finally:
        conn.close()

    for summary in summaries:
        print(summary)
        source = summary.get("source") or ""
        if "players-cache-stale" in str(source):
            print(
                "  Used stale local FantasyPros /players cache (API rate limit). "
                "Re-run without --refresh-fp after the limit resets for fresh data."
            )
        elif "players-cache" in str(source):
            print("  Used local FantasyPros /players cache (no /players API call).")
        if summary.get("status") == "fp_season_mismatch":
            print(f"  {summary.get('message')}")
            continue
        stats_n = summary.get("stats_lookup_players")
        if stats_n is not None and stats_n < 30:
            print(
                f"  Warning: only {stats_n} player(s) in {args.sport.upper()} season "
                f"{args.season} stats — run scripts/ingest_{args.sport}.py --season "
                f"{args.season} before rankings ingest."
            )
        unmapped_p = summary.get("draft_unmapped_players") or summary.get(
            "projection_unmapped_players"
        )
        raw_rows = summary.get("raw_rows") or 0
        if unmapped_p and raw_rows and unmapped_p > raw_rows // 3:
            print(
                f"  Note: {unmapped_p} unique FP player(s) had no name match in season stats "
                f"({summary.get('draft_unmapped') or summary.get('projection_unmapped')} "
                "raw rows unmapped; draft pulls ~6 position lists per player)."
            )
    if any(s.get("status") == "no_data" for s in summaries):
        print(
            f"\nTip: confirm {ENV_API_KEY} is set and the season exists in FantasyPros "
            f"for {args.sport.upper()} {args.season}."
        )


if __name__ == "__main__":
    main()
