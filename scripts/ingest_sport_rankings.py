#!/usr/bin/env python3
"""Ingest FantasyPros draft ECR, weekly ECR, and/or projections for MLB, NBA, or NHL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.rankings.fantasypros_client import FantasyProsAPIError, configure_fp_rate_limit  # noqa: E402
from src.rankings.fantasypros_config import ENV_API_KEY  # noqa: E402
from src.rankings.fantasypros_config import FP_PUBLIC_API_DAILY_CALL_LIMIT  # noqa: E402
from src.rankings.sport_ingest import (  # noqa: E402
    _parse_week_range,
    estimate_fp_api_calls,
    ingest_sport_draft_ecr,
    ingest_sport_projections,
    ingest_sport_weekly_ecr,
    plan_weekly_consensus_fetches,
    print_fp_api_budget_warning,
)
from src.sports.weekly_rollup import build_player_week_stats_for_season  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(
        description="Ingest FantasyPros rankings/projections for a sport season"
    )
    p.add_argument("--sport", choices=["nba", "mlb", "nhl", "nfl"], required=True)
    p.add_argument("--season", type=int, required=True)
    p.add_argument(
        "--draft-only",
        action="store_true",
        help="Only load draft ECR into ecr_draft",
    )
    p.add_argument(
        "--weekly",
        action="store_true",
        help="Load weekly ECR into ecr_weekly (experimental; not used in app UI)",
    )
    p.add_argument(
        "--weeks",
        default=None,
        help="Weekly range for --weekly, e.g. 1-26 or 1,3,5",
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
        default=None,
        help=(
            "Minimum seconds between live FantasyPros API calls (cache hits skip this). "
            "Default: 8 for --weekly, 2 otherwise."
        ),
    )
    p.add_argument(
        "--fp-min-interval",
        type=float,
        default=None,
        help=(
            "Global minimum seconds between any FP HTTP request (default 5, or max(delay, 5) for weekly). "
            "Overrides FANTASYPROS_MIN_INTERVAL_SEC when set."
        ),
    )
    p.add_argument(
        "--fp-429-wait",
        type=float,
        default=None,
        help="Base seconds to wait on HTTP 429 when Retry-After is missing (default 90).",
    )
    p.add_argument(
        "--refresh-fp",
        action="store_true",
        help="Re-download FantasyPros /players (ignore local cache)",
    )
    p.add_argument(
        "--refresh-fp-cache",
        action="store_true",
        help="Re-fetch consensus rankings even if data/cache/fantasypros/*.json exists",
    )
    p.add_argument(
        "--positional-boards",
        action="store_true",
        help=(
            "Use per-position consensus loops (3–5+ calls per draft/week). "
            "Avoid unless ALL boards fail — Public API is ~100 calls/day."
        ),
    )
    p.add_argument(
        "--weekly-positional-boards",
        action="store_true",
        help="Alias for --positional-boards when ingesting weekly ECR",
    )
    p.add_argument(
        "--rebuild-week-stats",
        action="store_true",
        help="Rebuild player_week_stats from game logs after ingest",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print weekly API plan (1 GET per week) without calling FantasyPros",
    )
    p.add_argument(
        "--weekly-source",
        choices=["consensus", "rankings"],
        default="consensus",
        help=(
            "Weekly ECR HTTP source: consensus-rankings (default, position=ALL&week=N) "
            "or /rankings?week=N (experimental — compare with compare_fp_weekly_endpoints.py first)"
        ),
    )
    args = p.parse_args()

    delay = args.delay if args.delay is not None else (8.0 if args.weekly else 2.0)
    min_interval = args.fp_min_interval if args.fp_min_interval is not None else max(delay, 8.0 if args.weekly else 2.0)
    configure_fp_rate_limit(
        min_interval_sec=min_interval,
        base_429_wait_sec=args.fp_429_wait,
    )

    if args.draft_only and args.projections_only:
        p.error("Use at most one of --draft-only and --projections-only")
    if args.draft_only and args.weekly:
        p.error("Use at most one of --draft-only and --weekly in a single run")

    positional = args.positional_boards or args.weekly_positional_boards
    week_list = _parse_week_range(args.weeks, sport_id=args.sport) if args.weeks else None

    if args.dry_run and not args.weekly:
        p.error("--dry-run requires --weekly")
    if args.weekly_source == "rankings" and positional:
        p.error("--positional-boards does not apply with --weekly-source rankings")

    if args.dry_run:
        from src.rankings.sport_ingest import max_fp_weeks, weekly_rankings_request_url

        weeks = week_list or list(range(1, max_fp_weeks(args.sport) + 1))
        est = estimate_fp_api_calls(
            args.sport,
            weekly_weeks=weeks,
            positional_boards=positional,
        )
        print(
            f"Dry run — daily limit ≈ {FP_PUBLIC_API_DAILY_CALL_LIMIT}, "
            f"uncached calls if no cache: up to {est['estimated_calls']}"
        )
        plan = plan_weekly_consensus_fetches(
            args.sport,
            args.season,
            weeks,
            positional_boards=positional,
            refresh_cache=args.refresh_fp_cache,
        )
        print(plan)
        for req in plan["requests"]:
            status = "cache" if req["cached"] else "API"
            if args.weekly_source == "rankings":
                req_url = weekly_rankings_request_url(
                    args.sport, args.season, int(req["week"])
                )
                print(f"  w{req['week']:>2}: {status} — {req_url}")
            else:
                print(f"  w{req['week']:>2} {req['position']}: {status} — {req['request']}")
        print(
            "\nParsing (positional reorder, player_id mapping, DuckDB insert) is local — "
            "no extra FantasyPros calls."
        )
        return

    print(
        f"FantasyPros Public API: ~{FP_PUBLIC_API_DAILY_CALL_LIMIT} calls/day per key. "
        "Default ingest uses position=ALL (one HTTP GET per draft or per week). "
        "Cached JSON under data/cache/fantasypros/ uses 0 calls."
    )
    print_fp_api_budget_warning(
        args.sport,
        draft=not args.weekly and not args.projections_only,
        weekly_weeks=week_list if args.weekly else None,
        projections=args.projections_only
        or (not args.draft_only and not args.weekly),
        positional_boards=positional,
        refresh_players=args.refresh_fp,
    )
    if args.weekly:
        print(
            f"Pacing: min_interval={min_interval:.1f}s between live API calls; "
            "re-run the same command to resume (cached weeks are free)."
        )

    init_schema()
    conn = get_connection()
    replace = not args.no_replace
    summaries: list[dict] = []

    try:
        if args.weekly:
            summaries.append(
                ingest_sport_weekly_ecr(
                    conn,
                    args.sport,
                    args.season,
                    weeks=week_list,
                    replace=replace,
                    delay_sec=delay,
                    positional_boards=positional,
                    weekly_source=args.weekly_source,
                    refresh_consensus_cache=args.refresh_fp_cache,
                )
            )
        if not args.projections_only and not args.weekly:
            summaries.append(
                ingest_sport_draft_ecr(
                    conn,
                    args.sport,
                    args.season,
                    replace=replace,
                    delay_sec=delay,
                    refresh_fp_cache=args.refresh_fp,
                    positional_boards=positional,
                    refresh_consensus_cache=args.refresh_fp_cache,
                )
            )
        if not args.draft_only and not args.weekly:
            summaries.append(
                ingest_sport_projections(
                    conn,
                    args.sport,
                    args.season,
                    projection_type=args.projection_type,
                    replace=replace,
                    delay_sec=delay,
                )
            )
    except FantasyProsAPIError as exc:
        print(exc)
        if "429" in str(exc):
            print(
                "FantasyPros rate limit — wait 60–90s, then retry with a slower pace, e.g.\n"
                f"  --delay 10 --fp-min-interval 10   (you used delay={delay})"
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
        if summary.get("status") in ("fp_season_mismatch", "unsupported_season"):
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
        ) or summary.get("weekly_unmapped_players")
        raw_rows = summary.get("raw_rows") or 0
        if unmapped_p and raw_rows and unmapped_p > raw_rows // 3:
            print(
                f"  Note: {unmapped_p} unique FP player(s) had no name match in season stats "
                f"({summary.get('draft_unmapped') or summary.get('projection_unmapped') or summary.get('weekly_unmapped')} "
                "raw rows unmapped)."
            )

    if args.rebuild_week_stats or args.weekly:
        init_schema()
        conn2 = get_connection()
        try:
            n = build_player_week_stats_for_season(conn2, args.sport, args.season)
            print({"week_stats_rows": n, "sport": args.sport, "season": args.season})
        finally:
            conn2.close()

    if any(s.get("status") == "no_data" for s in summaries):
        print(
            f"\nTip: confirm {ENV_API_KEY} is set and the season exists in FantasyPros "
            f"for {args.sport.upper()} {args.season}."
        )


if __name__ == "__main__":
    main()
