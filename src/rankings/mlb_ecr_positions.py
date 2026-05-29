"""Align MLB draft ECR pitcher rows with ingested SP/RP season roles."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.sports.mlb.positions import PITCHER_POSITIONS, is_pitcher_position
from src.sports.player_seasons import stats_table


def _pitcher_role_from_stats(
    lookup: pd.DataFrame,
    player_id: str,
) -> str | None:
    """Best SP/RP label from season stats (matches classify_pitcher_role ingest)."""
    pid = str(player_id).strip()
    sub = lookup[
        (lookup["player_id"].astype(str) == pid)
        & (lookup["position"].astype(str).str.upper().isin(PITCHER_POSITIONS))
    ]
    if sub.empty:
        return None
    roles = sub["position"].astype(str).str.upper().unique().tolist()
    if len(roles) == 1:
        return roles[0]
    if "games" in sub.columns:
        sub = sub.copy()
        sub["games"] = pd.to_numeric(sub["games"], errors="coerce").fillna(0)
        return str(sub.sort_values("games", ascending=False).iloc[0]["position"]).upper()
    return roles[0]


def sync_mlb_pitcher_ecr_positions(
    rankings: pd.DataFrame,
    conn: duckdb.DuckDBPyConnection,
    season: int,
) -> tuple[pd.DataFrame, int]:
    """
    Set ECR ``position`` to ingested SP/RP when we have a mapped ``player_id``.

    FantasyPros labels (or generic ``P``) can disagree with BRef GS/SV role split.
    """
    if rankings.empty or "player_id" not in rankings.columns:
        return rankings, 0

    lookup = conn.execute(
        f"""
        SELECT player_id, position, games
        FROM {stats_table("mlb")}
        WHERE season = ?
        """,
        [int(season)],
    ).df()
    if lookup.empty:
        return rankings, 0
    lookup.columns = [str(c).lower() for c in lookup.columns]

    out = rankings.copy()
    updated = 0
    for idx, row in out.iterrows():
        pid = row.get("player_id")
        if pd.isna(pid):
            continue
        role = _pitcher_role_from_stats(lookup, str(pid))
        if not role:
            continue
        current = str(row.get("position") or "").strip().upper()
        if not is_pitcher_position(current) and current not in ("", "NAN"):
            continue
        if current != role:
            out.at[idx, "position"] = role
            updated += 1
    return out, updated
