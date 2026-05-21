#!/usr/bin/env python3
"""Rebuild the players search index from season_stats (includes retired players)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import db_exists, get_connection  # noqa: E402
from src.db.maintenance import (  # noqa: E402
    rebuild_players_table,
    refresh_player_display_names,
)


def main() -> None:
    if not db_exists():
        print("No database at data/fantasy_tracker.duckdb — run ingest first.")
        sys.exit(1)
    conn = get_connection()
    try:
        before = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        rebuild_players_table(conn)
        after = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        print(f"players table: {before} -> {after} rows")
        refresh_player_display_names(conn)
        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
