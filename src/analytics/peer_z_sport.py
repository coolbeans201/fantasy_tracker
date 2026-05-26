"""Peer Z helpers for MLB / NBA / NHL."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.peer_z import peer_cohort_at_position, peer_z_score
from src.analytics.sport_variance import add_volume_flags_sport
from src.analytics.variance import load_thresholds
from src.sports.peer_positions import positions_for_peer_grouping
from src.sports.peer_queries import season_stats_for_peer_analysis


def peer_cohort_at_position_sport(
    peer_df: pd.DataFrame,
    sport_id: str,
    position: str | None,
) -> pd.DataFrame:
    if peer_df.empty or "position" not in peer_df.columns:
        return pd.DataFrame()
    if "peer_qualified" not in peer_df.columns:
        peer_df = add_volume_flags_sport(peer_df, sport_id)
    qualified = peer_df[peer_df["peer_qualified"]]
    pos = positions_for_peer_grouping(sport_id, position)
    if not pos:
        return pd.DataFrame()
    return qualified[qualified["position"] == pos]


def peer_z_score_sport(
    fantasy_points: float,
    peer_df: pd.DataFrame,
    sport_id: str,
    position: str | None,
    min_peers: int | None = None,
) -> float | None:
    thresholds = load_thresholds()
    min_peers = min_peers or thresholds.get("min_qualified_peers", 10)
    cohort = peer_cohort_at_position_sport(peer_df, sport_id, position)
    if len(cohort) < min_peers:
        return None
    mean = cohort["fantasy_points"].mean()
    std = cohort["fantasy_points"].std()
    if not std or std <= 0:
        return None
    return float((fantasy_points - mean) / std)


def add_peer_z_season_column_sport(
    df: pd.DataFrame,
    sport_id: str,
    *,
    min_games: int | None = None,
    fp_col: str = "fantasy_points",
) -> pd.DataFrame:
    out = df.copy()
    min_peers = load_thresholds().get("min_qualified_peers", 10)
    out["peer_z_season"] = np.nan
    if "position" in out.columns:
        out["position"] = out["position"].apply(
            lambda p: positions_for_peer_grouping(sport_id, p) if p is not None else p
        )
    flagged = add_volume_flags_sport(out, sport_id, min_games=min_games)
    qualified = flagged[flagged["peer_qualified"]]
    for pos, group in qualified.groupby("position"):
        if len(group) < min_peers:
            continue
        mean = group[fp_col].mean()
        std = group[fp_col].std()
        if std and std > 0:
            flagged.loc[group.index, "peer_z_season"] = (group[fp_col] - mean) / std
    return flagged


def add_peer_z_era_column_sport(
    df: pd.DataFrame,
    sport_id: str,
    all_seasons: pd.DataFrame,
    *,
    min_games: int | None = None,
    fp_col: str = "fantasy_points",
) -> pd.DataFrame:
    out = add_volume_flags_sport(df.copy(), sport_id, min_games=min_games)
    all_q = add_volume_flags_sport(all_seasons, sport_id, min_games=min_games)
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


def enrich_leaders_dataframe_sport(
    conn,
    sport_id: str,
    df: pd.DataFrame,
    season: int,
    *,
    positions: list[str] | None = None,
    min_games: int,
    era_z: bool = False,
) -> pd.DataFrame:
    del positions
    if df.empty:
        return df
    peer_df = season_stats_for_peer_analysis(
        conn, sport_id, season=season, min_games=min_games
    )
    peer_df = add_volume_flags_sport(peer_df, sport_id, min_games=min_games)
    out = df.copy()
    if "position" in out.columns:
        out["position"] = out["position"].apply(
            lambda p: positions_for_peer_grouping(sport_id, p) if p is not None else p
        )
    out["peer_z_season"] = out.apply(
        lambda r: peer_z_score_sport(
            r.get("fantasy_points", 0),
            peer_df,
            sport_id,
            r.get("position"),
        ),
        axis=1,
    )
    if not era_z:
        return out
    all_seasons = season_stats_for_peer_analysis(
        conn, sport_id, season=None, min_games=min_games
    )
    return add_peer_z_era_column_sport(out, sport_id, all_seasons, min_games=min_games)


def peer_df_for_entity_season_sport(
    conn,
    sport_id: str,
    season: int,
    min_games: int,
) -> pd.DataFrame:
    return season_stats_for_peer_analysis(
        conn, sport_id, season=season, min_games=min_games
    )
