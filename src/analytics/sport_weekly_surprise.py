"""Weekly ECR vs weekly finish rank for MLB / NBA / NHL."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.analytics.sport_surprise import (
    _collapse_mlb_qualified_by_role,
    _dedupe_mlb_ecr_by_role,
    _mlb_ecr_merge_role,
    _normalize_positions,
)
from src.analytics.sport_variance import qualifies_weekly_volume_sport
from src.analytics.surprise import assign_positional_ecr_ranks, assign_positional_ranks, ecr_ranks_look_overall
from src.analytics.weekly_surprise_tags import position_week_rank_delta_percentiles
from src.db.queries import load_ecr_weekly, load_player_week_stats, season_has_weekly_rankings
from src.sports.peer_positions import positions_for_peer_grouping
from src.sports.weekly_rollup import build_player_week_stats_for_season


def _ensure_week_stats(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
) -> pd.DataFrame:
    sid = str(sport_id).strip().lower()
    stats = load_player_week_stats(conn, sid, season)
    if stats.empty:
        build_player_week_stats_for_season(conn, sid, season, replace=True)
        stats = load_player_week_stats(conn, sid, season)
    return stats


def _merge_weekly_ecr_with_stats(
    qualified: pd.DataFrame,
    ecr: pd.DataFrame,
    sport_id: str,
) -> pd.DataFrame:
    if qualified.empty or ecr.empty:
        return pd.DataFrame()

    stats = _normalize_positions(qualified, sport_id)
    draft = _normalize_positions(ecr, sport_id)
    if ecr_ranks_look_overall(draft):
        draft = assign_positional_ecr_ranks(draft)

    sid = str(sport_id).strip().lower()
    if sid == "mlb":
        draft = _dedupe_mlb_ecr_by_role(draft)
        stats = stats.copy()
        stats["_merge_role"] = stats["position"].map(_mlb_ecr_merge_role)
        draft["_merge_role"] = draft["position"].map(_mlb_ecr_merge_role)
        merged = stats.merge(
            draft,
            on=["player_id", "season", "week", "_merge_role"],
            how="inner",
            suffixes=("", "_ecr"),
        )
        if merged.empty:
            return merged
        merged = merged.drop(
            columns=[c for c in ("_merge_role", "_merge_role_ecr", "position_ecr") if c in merged.columns],
            errors="ignore",
        )
        merged = merged.rename(columns={"ecr_rank": "weekly_ecr"})
        if "player_name_ecr" in merged.columns:
            merged["player_name"] = merged["player_name"].fillna(merged["player_name_ecr"])
        merged["rank_delta"] = merged["weekly_ecr"] - merged["finish_rank"]
        merged["surprise_qualified"] = True
        return merged

    merged = stats.merge(
        draft,
        on=["player_id", "season", "week", "position"],
        how="inner",
        suffixes=("", "_ecr"),
    )
    if merged.empty:
        return merged
    merged = merged.rename(columns={"ecr_rank": "weekly_ecr"})
    if "player_name_ecr" in merged.columns:
        merged["player_name"] = merged["player_name"].fillna(merged["player_name_ecr"])
    merged["rank_delta"] = merged["weekly_ecr"] - merged["finish_rank"]
    merged["surprise_qualified"] = True
    return merged


def compute_sport_weekly_surprise_for_season(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
    preset: str,  # noqa: ARG001
    position: str | None = None,
) -> pd.DataFrame:
    """All qualified player-weeks with weekly ECR, finish rank, and rank_delta."""
    sid = str(sport_id).strip().lower()
    if not season_has_weekly_rankings(conn, season, sport=sid):
        return pd.DataFrame()

    weekly = _ensure_week_stats(conn, sid, season)
    if weekly.empty:
        return pd.DataFrame()

    if position:
        pos_key = positions_for_peer_grouping(sid, position)
        weekly = weekly[weekly["position"] == pos_key]

    weekly = weekly.copy()
    weekly["week_qualified"] = weekly.apply(
        lambda r: qualifies_weekly_volume_sport(r, sid),
        axis=1,
    )

    ranked_parts: list[pd.DataFrame] = []
    for (_wk, _pos), group in weekly.groupby(["week", "position"]):
        qualified = group[group["week_qualified"]].copy()
        if qualified.empty:
            continue
        if sid == "mlb":
            qualified = _collapse_mlb_qualified_by_role(qualified)
        qualified = assign_positional_ranks(qualified, rank_col="finish_rank")
        ranked_parts.append(qualified)

    if not ranked_parts:
        return pd.DataFrame()

    ranked = pd.concat(ranked_parts, ignore_index=True)
    ecr = load_ecr_weekly(conn, season, position=position, sport=sid)
    if ecr.empty:
        return pd.DataFrame()

    merged = _merge_weekly_ecr_with_stats(ranked, ecr, sid)
    if merged.empty:
        return merged

    if "weekly_ecr" not in merged.columns and "draft_ecr" in merged.columns:
        merged["weekly_ecr"] = merged["draft_ecr"]
    merged["rank_delta"] = merged["weekly_ecr"] - merged["finish_rank"]
    return merged


def enrich_player_weeks_with_surprise(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    weekly: pd.DataFrame,
    season: int,
    preset: str,
    position: str | None,
) -> pd.DataFrame:
    """Add weekly_ecr, finish_rank, rank_delta to a player's weekly frame."""
    sid = str(sport_id).strip().lower()
    if weekly.empty or not season_has_weekly_rankings(conn, season, sport=sid):
        return weekly

    season_weekly = compute_sport_weekly_surprise_for_season(
        conn, sid, season, preset, position=position
    )
    if season_weekly.empty:
        return weekly

    player_ids = weekly["player_id"].astype(str).unique()
    subset = season_weekly[season_weekly["player_id"].astype(str).isin(player_ids)]
    attach = subset[
        ["week", "weekly_ecr", "finish_rank", "rank_delta"]
    ].drop_duplicates(subset=["week"])
    return weekly.merge(attach, on="week", how="left")


def season_weekly_surprise_for_entity_sport(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    entity_id: str,
    season: int,
    preset: str,
    *,
    position: str | None = None,
) -> dict | None:
    """Best weekly rank beat and beat-week count for profile header."""
    sid = str(sport_id).strip().lower()
    frame = compute_sport_weekly_surprise_for_season(
        conn, sid, season, preset, position=position
    )
    if frame.empty:
        return None
    rows = frame[frame["player_id"].astype(str) == str(entity_id)]
    if position is not None and "position" in rows.columns:
        if sid == "mlb":
            role = _mlb_ecr_merge_role(position)
            rows = rows[rows["position"].map(_mlb_ecr_merge_role) == role]
        else:
            pos_key = positions_for_peer_grouping(sid, position)
            rows = rows[rows["position"] == pos_key]
    if rows.empty:
        return None
    deltas = pd.to_numeric(rows["rank_delta"], errors="coerce").dropna()
    if deltas.empty:
        return None
    best = int(deltas.max())
    return {
        "best_weekly_rank_delta": best,
        "weeks_with_surprise": int(len(rows)),
    }


def cohort_rank_delta_percentiles_for_week(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
    preset: str,
    position: str,
    week: int,
) -> tuple[float | None, float | None]:
    frame = compute_sport_weekly_surprise_for_season(
        conn, sport_id, season, preset, position=position
    )
    if frame.empty:
        return None, None
    subset = frame[frame["week"].astype(int) == int(week)]
    return position_week_rank_delta_percentiles(subset)
