#!/usr/bin/env python3
"""Bulk-ingest completed seasons (default 1999–2025)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ingest_season import ingest_seasons  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk ingest NFL seasons")
    parser.add_argument("--from-year", type=int, default=1999)
    parser.add_argument("--to-year", type=int, default=2025)
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5,
        help="Ingest N seasons per batch to limit memory",
    )
    args = parser.parse_args()
    seasons = list(range(args.from_year, args.to_year + 1))
    chunk = args.chunk_size
    for i in range(0, len(seasons), chunk):
        batch = seasons[i : i + chunk]
        print(f"Batch {i // chunk + 1}: {batch[0]}–{batch[-1]}")
        ingest_seasons(batch)


if __name__ == "__main__":
    main()
