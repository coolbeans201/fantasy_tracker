#!/usr/bin/env python3
"""Print MLB position counts in DuckDB (diagnose sparse DH labels)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection  # noqa: E402


def main() -> None:
    conn = get_connection(read_only=True)
    try:
        print("=== mlb_player_season_stats by position (all seasons) ===")
        print(
            conn.execute(
                """
                SELECT position,
                       COUNT(*) AS rows,
                       COUNT(DISTINCT player_id) AS players
                FROM mlb_player_season_stats
                GROUP BY position
                ORDER BY players DESC
                """
            ).df().to_string(index=False)
        )
        for year in (2024, 2025):
            print(f"\n=== season {year} ===")
            print(
                conn.execute(
                    """
                    SELECT position, COUNT(DISTINCT player_id) AS players
                    FROM mlb_player_season_stats
                    WHERE season = ?
                    GROUP BY position
                    ORDER BY players DESC
                    """,
                    [year],
                ).df().to_string(index=False)
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
