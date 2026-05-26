"""Aggregate per-season leader rows into window totals (MLB/NBA/NHL + shared logic)."""

from __future__ import annotations

import pandas as pd


def aggregate_leader_window(per_season: pd.DataFrame) -> pd.DataFrame:
    """Sum qualified player-season rows into one row per player_id."""
    if per_season.empty:
        return per_season

    if "player_id" in per_season.columns:
        id_col = "player_id"
    elif "team" in per_season.columns:
        id_col = "team"
    else:
        return per_season

    stat_cols = [
        c
        for c in per_season.columns
        if c
        not in {
            id_col,
            "player_name",
            "position",
            "team",
            "teams",
            "season",
            "games",
            "fantasy_points",
        }
        and pd.api.types.is_numeric_dtype(per_season[c])
    ]

    agg: dict = {
        "player_name": ("player_name", "last"),
        "position": ("position", "last"),
        "seasons_in_window": ("season", "nunique"),
        "games": ("games", "sum"),
        "fantasy_points": ("fantasy_points", "sum"),
    }
    if "team" in per_season.columns:
        agg["team"] = ("team", "last")
    if "teams" in per_season.columns:
        agg["teams"] = ("teams", "last")
    for col in stat_cols:
        agg[col] = (col, "sum")

    grouped = per_season.groupby(id_col, as_index=False).agg(**agg)
    if "fantasy_points" in grouped.columns and "games" in grouped.columns:
        grouped["fp_per_game"] = grouped["fantasy_points"] / grouped["games"].replace(0, pd.NA)
    return grouped
