"""Compute fantasy points from weekly stat rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

PRESETS_PATH = Path(__file__).parent / "presets.yaml"

STAT_COLUMNS = [
    "passing_yards",
    "passing_tds",
    "interceptions",
    "rushing_yards",
    "rushing_tds",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "fumbles_lost",
    "carries",
    "targets",
]

SCORING_PRESETS = {
    "standard": "fantasy_points_standard",
    "half_ppr": "fantasy_points_half_ppr",
    "full_ppr": "fantasy_points_full_ppr",
}

DISPLAY_PRESETS = {
    "Standard": "standard",
    "Half-PPR": "half_ppr",
    "Full PPR": "full_ppr",
}


def load_presets() -> dict[str, dict[str, float]]:
    with PRESETS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def compute_fantasy_points(df: pd.DataFrame, preset_key: str) -> pd.Series:
    """Return weekly fantasy points for a preset."""
    presets = load_presets()
    if preset_key not in presets:
        raise ValueError(f"Unknown preset: {preset_key}")
    weights = presets[preset_key]

    total = pd.Series(0.0, index=df.index)
    for stat, weight in weights.items():
        if stat in df.columns and weight != 0:
            total += df[stat].fillna(0) * weight
    return total.round(2)


def apply_all_presets(df: pd.DataFrame) -> pd.DataFrame:
    """Add fantasy_points_* columns for all presets."""
    out = df.copy()
    for preset_key in load_presets():
        col = f"fantasy_points_{preset_key}"
        out[col] = compute_fantasy_points(out, preset_key)
    return out


def fp_column_for_preset(preset_key: str) -> str:
    if preset_key in SCORING_PRESETS:
        return SCORING_PRESETS[preset_key]
    return f"fantasy_points_{preset_key}"


def resolve_preset(display_or_key: str) -> str:
    if display_or_key in DISPLAY_PRESETS:
        return DISPLAY_PRESETS[display_or_key]
    if display_or_key in SCORING_PRESETS:
        return display_or_key
    raise ValueError(f"Unknown scoring preset: {display_or_key}")


def offensive_fp_column(preset: str) -> str:
    return fp_column_for_preset(resolve_preset(preset))


def fantasy_points_sql_expr(preset: str, prefix: str = "") -> str:
    """
    SQL expression for leaderboard fantasy points.
    Kickers use ESPN kicker points; other positions use the offensive preset.
    """
    p = f"{prefix}." if prefix else ""
    off_col = offensive_fp_column(preset)
    return (
        f"CASE WHEN {p}position = 'K' THEN {p}fantasy_points_kicker "
        f"ELSE {p}{off_col} END"
    )
