"""Derived season-level metrics from existing columns."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_fp_per_game(df: pd.DataFrame, fp_col: str = "fantasy_points") -> pd.DataFrame:
    """Add fp_per_game = fantasy_points / games (NaN when games is 0)."""
    out = df.copy()
    games = pd.to_numeric(out.get("games", 0), errors="coerce").fillna(0)
    fp = pd.to_numeric(out.get(fp_col, 0), errors="coerce")
    out["fp_per_game"] = np.where(games > 0, fp / games, np.nan)
    return out


def count_prime_seasons(career_df: pd.DataFrame, *, z_col: str = "career_z") -> int:
    """Qualified seasons with career Z above 1."""
    if career_df.empty or z_col not in career_df.columns:
        return 0
    qualified = career_df.get("peer_qualified", pd.Series(True, index=career_df.index))
    if "peer_qualified" in career_df.columns:
        mask = career_df["peer_qualified"] & (career_df[z_col] > 1)
    else:
        mask = career_df[z_col] > 1
    return int(mask.sum())


def peak_season_year(career_df: pd.DataFrame, fp_col: str = "fantasy_points") -> int | None:
    if career_df.empty or fp_col not in career_df.columns:
        return None
    idx = career_df[fp_col].idxmax()
    if pd.isna(idx):
        return None
    return int(career_df.loc[idx, "season"])
