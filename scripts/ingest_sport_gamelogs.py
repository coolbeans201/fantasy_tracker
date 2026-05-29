#!/usr/bin/env python3
"""Ingest per-game logs for MLB, NBA, or NHL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402

_INGESTERS = {
    "mlb": ("src.sports.mlb.gamelogs", "ingest_season_gamelogs", 6, 0.25),
    "nhl": ("src.sports.nhl.gamelogs", "ingest_season_gamelogs", 3, 0.65),
    "nba": ("src.sports.nba.gamelogs", "ingest_season_gamelogs", 1, 0.0),
}


def _load_ingest(sport: str):
    mod_path, fn_name, default_workers, default_delay = _INGESTERS[sport.strip().lower()]
    import importlib

    mod = importlib.import_module(mod_path)
    return getattr(mod, fn_name), default_workers, default_delay


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest sport player game logs")
    p.add_argument("--sport", required=True, choices=sorted(_INGESTERS))
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--limit-players", type=int, default=None)
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Parallel fetch workers (MLB/NHL; NBA uses bulk API).",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Per-request delay in seconds (MLB/NHL).",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not read/write data/cache/gamelogs/{sport}/{season}/.",
    )
    p.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore cached player files and refetch from APIs.",
    )
    p.add_argument(
        "--per-player-only",
        action="store_true",
        help="NBA only: skip bulk league download.",
    )
    args = p.parse_args()

    sport = args.sport.strip().lower()
    ingest_fn, default_workers, default_delay = _load_ingest(sport)
    workers = int(args.workers) if args.workers is not None else default_workers
    delay = float(args.delay) if args.delay is not None else default_delay

    init_schema()
    conn = get_connection()
    try:
        kwargs: dict = {
            "limit_players": args.limit_players,
        }
        if sport in ("mlb", "nhl"):
            kwargs.update(
                delay_sec=max(0.0, delay),
                workers=max(1, workers),
                use_cache=not args.no_cache,
                refresh_cache=args.refresh_cache,
            )
        elif sport == "nba" and args.per_player_only:
            kwargs["per_player_only"] = True

        summary = ingest_fn(conn, args.season, **kwargs)
        print(f"Ingested {sport.upper()} game logs for {args.season}: {summary}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
