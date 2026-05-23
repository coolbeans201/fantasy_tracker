"""Load FantasyPros ECR into DuckDB."""

from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import nflreadpy as nfl
import pandas as pd

from src.rankings.map_players import attach_player_ids, load_fantasypros_to_gsis
from src.rankings.normalize import prepare_draft_ecr, prepare_weekly_ecr


def _to_pandas(data) -> pd.DataFrame:
    if hasattr(data, "to_pandas"):
        return data.to_pandas()
    return pd.DataFrame(data)


def _insert_rankings(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    frame: pd.DataFrame,
    columns: list[str],
) -> int:
    if frame.empty:
        return 0
    subset = frame.copy()
    for col in columns:
        if col not in subset.columns:
            subset[col] = pd.NA
    subset = subset[columns]
    pk_cols = {
        "ecr_draft": ["player_id", "season", "position"],
        "ecr_weekly": ["player_id", "season", "week", "position"],
    }
    dedupe = pk_cols.get(table, columns[:3])
    subset = subset.drop_duplicates(subset=dedupe, keep="first")
    conn.register("_rankings_tmp", subset)
    cols_sql = ", ".join(columns)
    conn.execute(
        f"INSERT INTO {table} ({cols_sql}) SELECT {cols_sql} FROM _rankings_tmp"
    )
    conn.unregister("_rankings_tmp")
    return len(subset)


_DRAFT_COLS = [
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

_WEEKLY_COLS = _DRAFT_COLS[:3] + ["week"] + _DRAFT_COLS[3:]


def ingest_rankings_from_nflverse(
    conn: duckdb.DuckDBPyConnection,
    *,
    replace: bool = True,
) -> dict:
    """
    Download FantasyPros archive + latest weekly file; map to player_id; load DuckDB.
    """
    raw_all = _to_pandas(nfl.load_ff_rankings("all"))
    draft = prepare_draft_ecr(raw_all)
    weekly = prepare_weekly_ecr(raw_all)

    try:
        raw_week = _to_pandas(nfl.load_ff_rankings("week"))
        week_extra = prepare_weekly_ecr(raw_week)
        if not week_extra.empty:
            weekly = pd.concat([weekly, week_extra], ignore_index=True)
            if not weekly.empty:
                weekly = weekly.drop_duplicates(
                    subset=["season", "week", "fantasypros_id", "position"],
                    keep="last",
                )
    except Exception:
        pass

    fp_map = load_fantasypros_to_gsis()
    draft_mapped, draft_unmapped = attach_player_ids(draft, conn, fp_map)
    weekly_mapped, weekly_unmapped = attach_player_ids(weekly, conn, fp_map)

    if replace:
        conn.execute("DELETE FROM ecr_draft")
        conn.execute("DELETE FROM ecr_weekly")

    draft_n = _insert_rankings(conn, "ecr_draft", draft_mapped, _DRAFT_COLS)
    weekly_n = _insert_rankings(conn, "ecr_weekly", weekly_mapped, _WEEKLY_COLS)

    seasons = []
    if draft_n:
        seasons.extend(draft_mapped["season"].tolist())
    if weekly_n:
        seasons.extend(weekly_mapped["season"].tolist())

    conn.execute("DELETE FROM rankings_manifest")
    conn.execute(
        """
        INSERT INTO rankings_manifest
            (ingested_at, draft_rows, weekly_rows, seasons_min, seasons_max)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            datetime.now(timezone.utc),
            draft_n,
            weekly_n,
            int(min(seasons)) if seasons else None,
            int(max(seasons)) if seasons else None,
        ],
    )

    return {
        "draft_rows": draft_n,
        "weekly_rows": weekly_n,
        "draft_unmapped": draft_unmapped,
        "weekly_unmapped": weekly_unmapped,
    }
