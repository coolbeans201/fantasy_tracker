"""Draft ECR vs positional finish rank for MLB / NBA / NHL."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.analytics.surprise import (
    assign_positional_ecr_ranks,
    assign_positional_ranks,
    ecr_ranks_look_overall,
)
from src.analytics.sport_variance import add_volume_flags_sport
from src.db.queries import load_ecr_draft, season_has_rankings
from src.sports.peer_positions import positions_for_peer_grouping
from src.sports.peer_queries import season_stats_for_peer_analysis


def _normalize_positions(df: pd.DataFrame, sport_id: str) -> pd.DataFrame:
    out = df.copy()
    if "position" not in out.columns:
        return out
    out["position"] = out["position"].apply(
        lambda p: positions_for_peer_grouping(sport_id, p)
    )
    return out.dropna(subset=["position"])


def _merge_ecr_with_stats(
    qualified: pd.DataFrame,
    ecr: pd.DataFrame,
    sport_id: str,
) -> pd.DataFrame:
    """Inner merge on player + season + position; fallback when ECR has a single row per player."""
    if qualified.empty or ecr.empty:
        return pd.DataFrame()

    stats = _normalize_positions(qualified, sport_id)
    draft = _normalize_positions(ecr, sport_id)
    if stats.empty or draft.empty:
        return pd.DataFrame()

    if ecr_ranks_look_overall(draft):
        draft = assign_positional_ecr_ranks(draft)

    merged = stats.merge(
        draft,
        on=["player_id", "season", "position"],
        how="inner",
        suffixes=("", "_ecr"),
    )
    if merged.empty:
        return merged

    merged = merged.rename(columns={"ecr_rank": "draft_ecr"})
    if "player_name_ecr" in merged.columns:
        merged["player_name"] = merged["player_name"].fillna(merged["player_name_ecr"])
    merged["rank_delta"] = merged["draft_ecr"] - merged["finish_rank"]
    merged["surprise_qualified"] = True
    return merged


def compute_sport_season_surprise_frame(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
    preset: str,  # noqa: ARG001 — ESPN v1 for sports; kept for API parity with NFL
    *,
    min_games: int | None = None,
) -> pd.DataFrame:
    """
    Volume-qualified players with draft ECR, finish rank, and rank_delta.

    Finish rank is positional (#1 among qualified PGs, etc.). Draft ECR is
    re-ranked within position from FantasyPros (overall lists are converted).
    """
    sid = str(sport_id).strip().lower()
    if not season_has_rankings(conn, season, sport=sid):
        return pd.DataFrame()

    stats = season_stats_for_peer_analysis(
        conn, sid, season=season, min_games=min_games
    )
    if stats.empty:
        return pd.DataFrame()

    flagged = add_volume_flags_sport(stats, sid, min_games=min_games)
    qualified = flagged[flagged["peer_qualified"]].copy()
    if qualified.empty:
        return pd.DataFrame()

    qualified = assign_positional_ranks(qualified)
    ecr = load_ecr_draft(conn, season, sport=sid)
    if ecr.empty:
        return pd.DataFrame()

    merged = _merge_ecr_with_stats(qualified, ecr, sid)
    if merged.empty:
        return pd.DataFrame()

    cols = [
        "player_id",
        "player_name",
        "season",
        "position",
        "fantasy_points",
        "games",
        "draft_ecr",
        "finish_rank",
        "rank_delta",
        "surprise_qualified",
    ]
    if "player_name" not in merged.columns:
        merged["player_name"] = merged.get("player_name_ecr")
    return merged[[c for c in cols if c in merged.columns]]


def enrich_leaders_with_surprise_sport(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    df: pd.DataFrame,
    season: int,
    preset: str,
    *,
    min_games: int | None = None,
    surprise_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach draft_ecr, finish_rank, rank_delta to a season leaders dataframe."""
    sid = str(sport_id).strip().lower()
    if df.empty or not season_has_rankings(conn, season, sport=sid):
        return df

    surprise = surprise_df
    if surprise is None:
        surprise = compute_sport_season_surprise_frame(
            conn, sid, season, preset, min_games=min_games
        )
    if surprise.empty:
        return df

    attach_cols = ["player_id", "draft_ecr", "finish_rank", "rank_delta", "surprise_qualified"]
    if "position" in df.columns and "position" in surprise.columns:
        attach_cols.insert(1, "position")
        subset = ["player_id", "position"]
    else:
        subset = ["player_id"]

    attach = surprise[attach_cols].drop_duplicates(subset=subset)
    out = df.copy()
    if "position" in attach.columns and "position" in out.columns:
        out["position"] = out["position"].apply(
            lambda p: positions_for_peer_grouping(sid, p)
        )
        return out.merge(attach, on=subset, how="left")
    return out.merge(attach.drop(columns=["position"], errors="ignore"), on=["player_id"], how="left")


def season_surprise_for_entity_sport(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    entity_id: str,
    season: int,
    preset: str,
    *,
    min_games: int | None = None,
    position: str | None = None,
) -> dict | None:
    """One player's season surprise metrics, or None if not qualified / no ECR."""
    sid = str(sport_id).strip().lower()
    frame = compute_sport_season_surprise_frame(
        conn, sid, season, preset, min_games=min_games
    )
    if frame.empty:
        return None
    rows = frame[frame["player_id"].astype(str) == str(entity_id)]
    if position is not None and "position" in rows.columns:
        pos_key = positions_for_peer_grouping(sid, position)
        rows = rows[rows["position"] == pos_key]
    if rows.empty:
        return None
    r = rows.iloc[0]
    return {
        "draft_ecr": int(r["draft_ecr"]),
        "finish_rank": int(r["finish_rank"]),
        "rank_delta": int(r["rank_delta"]),
    }


def format_sport_surprise_caption(sport_id: str) -> str:
    from src.sports.registry import get_sport

    label = get_sport(sport_id).label
    return (
        f"Draft rank vs finish uses FantasyPros expert consensus (ECR) for {label}. "
        "Both draft and finish ranks are **within position** (PG vs PG, etc.). "
        "Draft boards are fetched per position from FantasyPros; overall ranks are "
        "converted when needed. "
        "Only volume-qualified seasons count. "
        "Positive **rank Δ** = finished better than draft rank (lower rank is better)."
    )
