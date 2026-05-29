"""Shared DuckDB insert helpers for rankings tables."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pandas as pd

DRAFT_COLS = [
    "sport",
    "player_id",
    "season",
    "position",
    "ecr_rank",
    "ecr_sd",
    "player_name",
    "team",
    "fantasypros_id",
    "scrape_date",
]

PROJECTION_COLS = [
    "sport",
    "player_id",
    "fantasypros_id",
    "season",
    "week",
    "projection_type",
    "position",
    "player_name",
    "team",
    "projected_points",
    "stats_json",
    "ingested_at",
]


def insert_ecr_draft(
    conn: duckdb.DuckDBPyConnection,
    frame: pd.DataFrame,
) -> int:
    if frame.empty:
        return 0
    subset = frame.copy()
    for col in DRAFT_COLS:
        if col not in subset.columns:
            subset[col] = pd.NA
    subset = subset[DRAFT_COLS]
    subset = subset.drop_duplicates(subset=["sport", "player_id", "season", "position"], keep="first")
    conn.register("_ecr_draft_tmp", subset)
    cols_sql = ", ".join(DRAFT_COLS)
    conn.execute(f"INSERT INTO ecr_draft ({cols_sql}) SELECT {cols_sql} FROM _ecr_draft_tmp")
    conn.unregister("_ecr_draft_tmp")
    return len(subset)


def insert_fp_projections(
    conn: duckdb.DuckDBPyConnection,
    frame: pd.DataFrame,
) -> int:
    if frame.empty:
        return 0
    subset = frame.copy()
    if "ingested_at" not in subset.columns:
        subset["ingested_at"] = datetime.now(timezone.utc)
    for col in PROJECTION_COLS:
        if col not in subset.columns:
            subset[col] = pd.NA
    subset = subset[PROJECTION_COLS]
    dedupe = ["sport", "fantasypros_id", "season", "week", "projection_type", "position"]
    subset = subset.drop_duplicates(subset=dedupe, keep="first")
    conn.register("_fp_proj_tmp", subset)
    cols_sql = ", ".join(PROJECTION_COLS)
    conn.execute(
        f"INSERT INTO fp_projections ({cols_sql}) SELECT {cols_sql} FROM _fp_proj_tmp"
    )
    conn.unregister("_fp_proj_tmp")
    return len(subset)
