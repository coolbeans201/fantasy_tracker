"""Peer Z-score helpers (separate module for reliable imports)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.variance import add_volume_flags, load_thresholds
from src.db.queries import (
    dst_season_stats_for_peer_analysis,
    season_stats_for_peer_analysis,
)
from src.positions import (
    DST_POSITION,
    OFFENSE_POSITIONS,
    is_dst_only_selection,
    is_dst_position,
    is_kicker_only_selection,
    positions_for_peer_grouping,
)


def peer_cohort_at_position(
    peer_df: pd.DataFrame,
    position: str | None,
) -> pd.DataFrame:
    """Qualified peers for one fantasy position in a season cohort."""
    if peer_df.empty or "position" not in peer_df.columns:
        return pd.DataFrame()
    if "peer_qualified" not in peer_df.columns:
        peer_df = add_volume_flags(peer_df)
    qualified = peer_df[peer_df["peer_qualified"]]
    pos = positions_for_peer_grouping(position)
    if not pos:
        return pd.DataFrame()
    return qualified[qualified["position"] == pos]


def peer_z_score(
    fantasy_points: float,
    peer_df: pd.DataFrame,
    position: str | None,
    min_peers: int | None = None,
) -> float | None:
    """Z-score for one player's season FP vs qualified peers at their position."""
    thresholds = load_thresholds()
    min_peers = min_peers or thresholds.get("min_qualified_peers", 10)
    cohort = peer_cohort_at_position(peer_df, position)
    if len(cohort) < min_peers:
        return None
    mean = cohort["fantasy_points"].mean()
    std = cohort["fantasy_points"].std()
    if not std or std <= 0:
        return None
    return float((fantasy_points - mean) / std)


def add_peer_z_season_column(
    df: pd.DataFrame,
    *,
    min_games: int | None = None,
    fp_col: str = "fantasy_points",
    dst_cohort: bool = False,
) -> pd.DataFrame:
    """
    Add peer_z_season to a leaderboard-style dataframe with position + fantasy_points.

    When dst_cohort is True, every row is compared to all teams in the frame (no min-games gate).
    """
    out = df.copy()
    min_peers = load_thresholds().get("min_qualified_peers", 10)
    out["peer_z_season"] = np.nan

    if dst_cohort:
        if len(out) < min_peers:
            return out
        mean = out[fp_col].mean()
        std = out[fp_col].std()
        if std and std > 0:
            out["peer_z_season"] = (out[fp_col] - mean) / std
        return out

    flagged = add_volume_flags(out, min_games=min_games)
    qualified = flagged[flagged["peer_qualified"]]
    for pos, group in qualified.groupby("position"):
        if len(group) < min_peers:
            continue
        mean = group[fp_col].mean()
        std = group[fp_col].std()
        if std and std > 0:
            flagged.loc[group.index, "peer_z_season"] = (group[fp_col] - mean) / std
    return flagged


def add_peer_z_era_column(
    df: pd.DataFrame,
    all_seasons: pd.DataFrame,
    *,
    min_games: int | None = None,
    fp_col: str = "fantasy_points",
) -> pd.DataFrame:
    """Merge peer_z_era from a historical qualified cohort."""
    out = add_volume_flags(df.copy(), min_games=min_games)
    all_q = add_volume_flags(all_seasons, min_games=min_games)
    era_stats = (
        all_q[all_q["peer_qualified"]]
        .groupby("position")[fp_col]
        .agg(era_mean="mean", era_std="std")
        .reset_index()
    )
    out = out.merge(era_stats, on="position", how="left")
    out["peer_z_era"] = np.where(
        (out["era_std"] > 0) & out["peer_qualified"],
        (out[fp_col] - out["era_mean"]) / out["era_std"],
        np.nan,
    )
    return out.drop(columns=["era_mean", "era_std"], errors="ignore")


def enrich_leaders_dataframe(
    conn,
    df: pd.DataFrame,
    season: int,
    preset: str,
    positions: list[str],
    min_games: int,
    *,
    era_z: bool = False,
) -> pd.DataFrame:
    """Apply season (and optional era) peer Z columns to a season_leaders result."""
    if df.empty:
        return df

    if is_dst_only_selection(positions):
        return add_peer_z_season_column(df, dst_cohort=True)

    df = add_peer_z_season_column(df, min_games=min_games)

    if not era_z:
        return df

    if is_kicker_only_selection(positions):
        all_seasons = season_stats_for_peer_analysis(
            conn, season=None, preset=preset, min_games=min_games
        )
        all_seasons = all_seasons[all_seasons["position"] == "K"]
    else:
        all_seasons = season_stats_for_peer_analysis(
            conn, season=None, preset=preset, min_games=min_games
        )
        all_seasons = all_seasons[all_seasons["position"].isin(OFFENSE_POSITIONS)]

    return add_peer_z_era_column(df, all_seasons, min_games=min_games)


def peer_df_for_entity_season(
    conn,
    season: int,
    preset: str,
    position: str | None,
    min_games: int,
) -> pd.DataFrame:
    """Peer cohort dataframe for Profile / Compare."""
    if is_dst_position(position):
        return dst_season_stats_for_peer_analysis(conn, season=season)
    return season_stats_for_peer_analysis(
        conn, season=season, preset=preset, min_games=min_games
    )
