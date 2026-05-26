"""Draft ECR ingest for non-NFL sports (FantasyPros API spike)."""

from __future__ import annotations

import duckdb


def ingest_draft_ecr_stub(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
) -> dict:
    """
    Placeholder until FantasyPros API key + player ID mapping is wired.

    Returns summary dict for CLI reporting.
    """
    del conn, season
    return {
        "sport": sport_id,
        "status": "not_implemented",
        "message": "Configure FantasyPros API and player ID map (see docs/MULTISPORT_ROADMAP.md).",
    }
