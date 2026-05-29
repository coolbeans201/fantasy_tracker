#!/usr/bin/env python3
"""
Bulk-ingest MLB and NHL player game logs into DuckDB.

MLB regular-season game logs default from 2008 (aligns with BRef season stats).
NHL regular-season game logs default from 2005 (aligns with nhlpy season ingest).

Requires season stats already ingested for each year
(``ingest_mlb.py`` / ``ingest_nhl.py``) so player lists exist.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402

MLB_GAMELOG_FROM_YEAR = 2008
NHL_GAMELOG_FROM_YEAR = 2005

_SPORT_DEFAULTS: dict[str, tuple[int, int, int, float]] = {
    # sport -> (from_year, default_workers, default_delay sec between NHL API calls)
    "mlb": (MLB_GAMELOG_FROM_YEAR, 6, 0.25),
    "nhl": (NHL_GAMELOG_FROM_YEAR, 3, 0.65),
}


def _load_ingest(sport: str):
    import importlib

    mod_path = f"src.sports.{sport}.gamelogs"
    mod = importlib.import_module(mod_path)
    return getattr(mod, "ingest_season_gamelogs")


def _years(from_year: int, to_year: int) -> list[int]:
    if from_year > to_year:
        raise ValueError(f"from-year {from_year} > to-year {to_year}")
    return list(range(from_year, to_year + 1))


def _ingest_sport_range(
    conn,
    sport: str,
    years: list[int],
    *,
    workers: int,
    delay_sec: float,
    use_cache: bool,
    refresh_cache: bool,
    limit_players: int | None,
    fail_fast: bool,
    season_pause_sec: float,
) -> None:
    ingest_fn = _load_ingest(sport)
    failures: list[int] = []

    for end_year in years:
        print(f"\n=== {sport.upper()} game logs — season {end_year} ===")
        try:
            summary = ingest_fn(
                conn,
                end_year,
                limit_players=limit_players,
                delay_sec=delay_sec,
                workers=workers,
                use_cache=use_cache,
                refresh_cache=refresh_cache,
            )
            print(
                f"  OK {end_year}: {summary.get('rows', 0)} rows, "
                f"{summary.get('players_loaded', 0)}/"
                f"{summary.get('players_total', 0)} players"
            )
        except Exception as exc:
            if fail_fast:
                raise
            print(f"  WARNING: skipped {sport.upper()} {end_year}: {exc}")
            failures.append(end_year)
        if season_pause_sec > 0:
            time.sleep(season_pause_sec)

    if failures:
        print(f"\n{sport.upper()} skipped seasons ({len(failures)}): {failures}")


def main() -> None:
    current_year = date.today().year
    p = argparse.ArgumentParser(
        description="Bulk ingest MLB and NHL player game logs (regular season)."
    )
    p.add_argument(
        "--sport",
        choices=("mlb", "nhl", "both"),
        default="both",
        help="Which sport(s) to ingest (default: both).",
    )
    p.add_argument(
        "--to-year",
        type=int,
        default=current_year,
        help=f"Last season end year (default: {current_year}).",
    )
    p.add_argument(
        "--mlb-from-year",
        type=int,
        default=MLB_GAMELOG_FROM_YEAR,
        help=f"First MLB season year (default: {MLB_GAMELOG_FROM_YEAR}).",
    )
    p.add_argument(
        "--nhl-from-year",
        type=int,
        default=NHL_GAMELOG_FROM_YEAR,
        help=f"First NHL season end year (default: {NHL_GAMELOG_FROM_YEAR}).",
    )
    p.add_argument("--limit-players", type=int, default=None)
    p.add_argument("--workers", type=int, default=None, help="Parallel workers per sport.")
    p.add_argument("--delay", type=float, default=None, help="Per-request delay (seconds).")
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip data/cache/gamelogs/ read/write.",
    )
    p.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Refetch every player even if cache files exist.",
    )
    p.add_argument(
        "--season-pause",
        type=float,
        default=2.0,
        help="Seconds to pause between seasons (default: 2).",
    )
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first season error (default: skip and continue).",
    )
    args = p.parse_args()

    sports: list[str] = []
    if args.sport in ("mlb", "both"):
        sports.append("mlb")
    if args.sport in ("nhl", "both"):
        sports.append("nhl")

    init_schema()
    conn = get_connection()
    try:
        for sport in sports:
            default_from, default_workers, default_delay = _SPORT_DEFAULTS[sport]
            from_year = (
                args.mlb_from_year if sport == "mlb" else args.nhl_from_year
            )
            years = _years(from_year, args.to_year)
            workers = int(args.workers) if args.workers is not None else default_workers
            delay = float(args.delay) if args.delay is not None else default_delay

            print(
                f"\n{'#' * 60}\n"
                f"# {sport.upper()} game logs: {from_year}–{args.to_year} "
                f"({len(years)} seasons)\n"
                f"{'#' * 60}"
            )
            _ingest_sport_range(
                conn,
                sport,
                years,
                workers=max(1, workers),
                delay_sec=max(0.0, delay),
                use_cache=not args.no_cache,
                refresh_cache=args.refresh_cache,
                limit_players=args.limit_players,
                fail_fast=args.fail_fast,
                season_pause_sec=max(0.0, float(args.season_pause)),
            )
    finally:
        conn.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
