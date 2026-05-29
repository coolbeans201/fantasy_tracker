"""Draft / weekly ECR vs actual finish rank (volume-qualified)."""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from src.analytics.variance import add_volume_flags, qualifies_weekly_volume
from src.db.queries import (
    dst_season_stats_for_peer_analysis,
    load_ecr_draft,
    load_ecr_weekly,
    season_has_rankings,
    season_stats_for_peer_analysis,
    weekly_stats_for_surprise,
)
from src.entities import is_dst_entity, make_dst_entity_id
from src.positions import DST_POSITION, is_dst_position


def ecr_ranks_look_overall(draft: pd.DataFrame) -> bool:
    """True when raw ECR values look like an overall list, not a position board."""
    if draft.empty or "ecr_rank" not in draft.columns or "position" not in draft.columns:
        return False
    ranks = pd.to_numeric(draft["ecr_rank"], errors="coerce")
    for _pos, group in draft.groupby("position", dropna=False):
        g_ranks = ranks.loc[group.index].dropna()
        if g_ranks.empty:
            continue
        if float(g_ranks.max()) > max(120, len(g_ranks) * 1.5):
            return True
    return False


def assign_positional_ecr_ranks(
    df: pd.DataFrame,
    *,
    rank_col: str = "ecr_rank",
    out_col: str | None = None,
) -> pd.DataFrame:
    """
    Within each position, rank players by raw ECR (ascending: lower = better).

    Use when the source list is overall (e.g. FantasyPros MLB ``ALL``) so draft
    rank is comparable to positional finish rank.
    """
    out = df.copy()
    if out.empty or rank_col not in out.columns:
        return out
    target = out_col or rank_col
    raw = pd.to_numeric(out[rank_col], errors="coerce")
    out[target] = np.nan
    for _pos, group in out.groupby("position", dropna=False):
        out.loc[group.index, target] = raw.loc[group.index].rank(
            ascending=True, method="min"
        )
    out[target] = pd.to_numeric(out[target], errors="coerce")
    return out


def assign_positional_ranks(
    df: pd.DataFrame,
    *,
    fp_col: str = "fantasy_points",
    rank_col: str = "finish_rank",
) -> pd.DataFrame:
    """Rank 1 = highest fantasy points within each position group."""
    out = df.copy()
    out[rank_col] = np.nan
    if out.empty or fp_col not in out.columns:
        return out
    for _pos, group in out.groupby("position", dropna=False):
        out.loc[group.index, rank_col] = group[fp_col].rank(
            ascending=False, method="min"
        )
    out[rank_col] = pd.to_numeric(out[rank_col], errors="coerce")
    return out


def _ensure_player_id_column(df: pd.DataFrame) -> pd.DataFrame:
    """Leaders frames use player_id; DST rows only have team until we map them."""
    out = df.copy()
    if "player_id" not in out.columns:
        out["player_id"] = pd.NA
    missing = out["player_id"].isna()
    if missing.any() and "team" in out.columns:
        out.loc[missing, "player_id"] = (
            out.loc[missing, "team"].astype(str).str.strip().str.upper().map(make_dst_entity_id)
        )
    if out["player_id"].isna().all() and "entity_id" in out.columns:
        out["player_id"] = out["entity_id"]
    return out


def compute_season_surprise_frame(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    preset: str,
    *,
    min_games: int | None = None,
    include_dst: bool = True,
) -> pd.DataFrame:
    """
    Volume-qualified players with draft ECR, finish rank, and rank_delta.

    rank_delta = draft_ecr - finish_rank (positive = outperformed draft rank).
    """
    if not season_has_rankings(conn, season, sport="nfl"):
        return pd.DataFrame()

    stats = season_stats_for_peer_analysis(conn, season, preset, min_games=min_games)
    if stats.empty:
        return pd.DataFrame()

    flagged = add_volume_flags(stats, min_games=min_games)
    qualified = flagged[flagged["peer_qualified"]].copy()
    if qualified.empty:
        return pd.DataFrame()

    qualified = assign_positional_ranks(qualified)
    ecr = load_ecr_draft(conn, season, sport="nfl")
    if ecr.empty:
        return pd.DataFrame()

    merged = qualified.merge(
        ecr,
        on=["player_id", "season", "position"],
        how="inner",
        suffixes=("", "_ecr"),
    )
    merged = merged.rename(columns={"ecr_rank": "draft_ecr"})
    merged["rank_delta"] = merged["draft_ecr"] - merged["finish_rank"]
    merged["surprise_qualified"] = True

    if include_dst:
        dst_stats = dst_season_stats_for_peer_analysis(conn, season)
        dst_ecr = ecr[ecr["position"] == DST_POSITION]
        if not dst_stats.empty and not dst_ecr.empty:
            dst_stats = dst_stats.copy()
            dst_stats["player_id"] = dst_stats["player_id"].astype(str).map(make_dst_entity_id)
            dst_ranked = assign_positional_ranks(dst_stats)
            dst_merged = dst_ranked.merge(
                dst_ecr,
                on=["player_id", "season", "position"],
                how="inner",
            )
            if not dst_merged.empty:
                dst_merged = dst_merged.rename(columns={"ecr_rank": "draft_ecr"})
                dst_merged["rank_delta"] = dst_merged["draft_ecr"] - dst_merged["finish_rank"]
                dst_merged["surprise_qualified"] = True
                merged = pd.concat([merged, dst_merged], ignore_index=True)

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
    for c in cols:
        if c not in merged.columns and c == "player_name":
            merged["player_name"] = merged.get("player_name_ecr", merged.get("player_name"))
    return merged[[c for c in cols if c in merged.columns]]


def enrich_leaders_with_surprise(
    conn: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    season: int,
    preset: str,
    *,
    min_games: int | None = None,
    include_dst: bool = False,
    surprise_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach draft_ecr, finish_rank, rank_delta to a season_leaders dataframe."""
    if df.empty or not season_has_rankings(conn, season, sport="nfl"):
        return df

    surprise = surprise_df
    if surprise is None:
        surprise = compute_season_surprise_frame(
            conn, season, preset, min_games=min_games, include_dst=include_dst
        )
    if surprise.empty:
        return df

    attach = surprise[
        ["player_id", "draft_ecr", "finish_rank", "rank_delta", "surprise_qualified"]
    ].drop_duplicates(subset=["player_id"])
    out_df = _ensure_player_id_column(df)
    return out_df.merge(attach, on="player_id", how="left")


def season_surprise_for_entity(
    conn: duckdb.DuckDBPyConnection,
    entity_id: str,
    season: int,
    preset: str,
    *,
    min_games: int | None = None,
) -> dict | None:
    """One player's season surprise metrics, or None if not qualified / no ECR."""
    frame = compute_season_surprise_frame(
        conn,
        season,
        preset,
        min_games=min_games,
        include_dst=is_dst_entity(entity_id),
    )
    if frame.empty:
        return None
    row = frame[frame["player_id"] == entity_id]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "draft_ecr": int(r["draft_ecr"]),
        "finish_rank": int(r["finish_rank"]),
        "rank_delta": int(r["rank_delta"]),
    }


def top_surprise_slices(
    surprise_df: pd.DataFrame,
    *,
    n: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (outperformers, underperformers) by rank_delta."""
    if surprise_df.empty or "rank_delta" not in surprise_df.columns:
        return pd.DataFrame(), pd.DataFrame()
    qualified = surprise_df[surprise_df.get("surprise_qualified", True) == True]  # noqa: E712
    if qualified.empty:
        return pd.DataFrame(), pd.DataFrame()
    outperformers = qualified.nlargest(n, "rank_delta")
    underperformers = qualified.nsmallest(n, "rank_delta")
    return outperformers, underperformers


def compute_weekly_surprise_for_season(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    preset: str,
    position: str | None,
) -> pd.DataFrame:
    """All player-weeks with weekly ECR, finish rank, rank_delta (qualified weeks only)."""
    if not season_has_rankings(conn, season, sport="nfl"):
        return pd.DataFrame()

    weekly = weekly_stats_for_surprise(conn, season, preset, position)
    ecr = load_ecr_weekly(conn, season, position)
    if weekly.empty or ecr.empty:
        return pd.DataFrame()

    weekly = weekly.copy()
    weekly["week_qualified"] = weekly.apply(qualifies_weekly_volume, axis=1)
    ranked_parts: list[pd.DataFrame] = []
    for (wk, pos), group in weekly.groupby(["week", "position"]):
        qualified = group[group["week_qualified"]].copy()
        if qualified.empty:
            continue
        qualified = assign_positional_ranks(qualified, rank_col="finish_rank")
        ranked_parts.append(qualified)
    if not ranked_parts:
        return pd.DataFrame()
    ranked = pd.concat(ranked_parts, ignore_index=True)

    merged = ranked.merge(
        ecr,
        on=["player_id", "season", "week", "position"],
        how="inner",
    )
    merged = merged.rename(columns={"ecr_rank": "weekly_ecr"})
    merged["rank_delta"] = merged["weekly_ecr"] - merged["finish_rank"]
    return merged


def enrich_weekly_with_surprise(
    conn: duckdb.DuckDBPyConnection,
    weekly: pd.DataFrame,
    season: int,
    preset: str,
    position: str | None,
) -> pd.DataFrame:
    """Add weekly_ecr, finish_rank, rank_delta to a player weekly frame."""
    if weekly.empty or is_dst_position(position) or not season_has_rankings(
        conn, season, sport="nfl"
    ):
        return weekly

    season_weekly = compute_weekly_surprise_for_season(conn, season, preset, position)
    if season_weekly.empty:
        return weekly

    attach = season_weekly[
        ["week", "weekly_ecr", "finish_rank", "rank_delta"]
    ].drop_duplicates(subset=["week"])
    out = weekly.merge(attach, on="week", how="left")
    return out


def format_surprise_caption() -> str:
    return (
        "Draft rank vs finish uses FantasyPros expert consensus (ECR) from nflverse. "
        "Only volume-qualified seasons/weeks count — injured or low-usage players are "
        "excluded so a missed season does not count as a flop. "
        "Positive **rank Δ** = finished better than draft rank (lower rank number is better)."
    )
