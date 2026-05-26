#!/usr/bin/env python3
"""Ingest draft ECR for MLB/NBA/NHL (stub until API wired)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.rankings.sport_ingest import ingest_draft_ecr_stub  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest sport draft ECR (stub)")
    p.add_argument("--sport", choices=["nba", "mlb", "nhl"], required=True)
    p.add_argument("--season", type=int, required=True)
    args = p.parse_args()
    init_schema()
    conn = get_connection()
    try:
        summary = ingest_draft_ecr_stub(conn, args.sport, args.season)
    finally:
        conn.close()
    print(summary)


if __name__ == "__main__":
    main()
