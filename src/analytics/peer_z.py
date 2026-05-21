"""Peer Z-score helpers (separate module for reliable imports)."""

from __future__ import annotations

import pandas as pd

from src.analytics.variance import add_volume_flags, load_thresholds
from src.positions import positions_for_peer_grouping


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
