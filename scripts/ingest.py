#!/usr/bin/env python3
"""Unified ingest entrypoint: python scripts/ingest.py --sport nfl --season 2023"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest completed season data by sport")
    p.add_argument("--sport", choices=("nfl", "mlb", "nba", "nhl"), default="nfl")
    p.add_argument("--season", type=int, action="append", help="Season year (repeatable)")
    p.add_argument("--bulk", action="store_true", help="Bulk ingest (--from-year / --to-year)")
    p.add_argument("--from-year", type=int, default=2008)
    p.add_argument("--to-year", type=int, default=2025)
    p.add_argument(
        "--source",
        choices=("auto", "bref", "fangraphs"),
        default="auto",
        help="MLB only: baseball_reference vs fangraphs",
    )
    args = p.parse_args()
    scripts = {
        "nfl": ROOT / "scripts" / "ingest_season.py",
        "mlb": ROOT / "scripts" / "ingest_mlb.py",
        "nba": ROOT / "scripts" / "ingest_nba.py",
        "nhl": ROOT / "scripts" / "ingest_nhl.py",
    }
    script = scripts[args.sport]
    if args.bulk and args.sport in ("nfl", "mlb", "nba", "nhl"):
        cmd = [
            PY,
            str(script),
            "--bulk",
            "--from-year",
            str(args.from_year),
            "--to-year",
            str(args.to_year),
        ]
        if args.sport == "mlb":
            cmd.extend(["--source", args.source])
    elif args.season:
        for season in args.season:
            cmd = [PY, str(script), "--season", str(season)]
            if args.sport == "mlb":
                cmd.extend(["--source", args.source])
            code = subprocess.call(cmd)
            if code != 0:
                raise SystemExit(code)
        raise SystemExit(0)
    else:
        p.error("Provide --season or --bulk")
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
