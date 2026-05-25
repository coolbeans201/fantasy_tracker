"""Kicker and D/ST fantasy scoring (ESPN default; separate from offensive presets)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

KICKER_PRESETS_PATH = Path(__file__).parent / "kicker_presets.yaml"
DST_PRESETS_PATH = Path(__file__).parent / "dst_presets.yaml"

KICKER_FP_COLUMN = "fantasy_points_kicker"
DST_FP_COLUMN = "fantasy_points_dst"


def load_kicker_preset() -> dict[str, float]:
    with KICKER_PRESETS_PATH.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return {k: float(v) for k, v in raw.items()}


def load_dst_preset() -> dict:
    with DST_PRESETS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_dst_tier(tier: str) -> tuple[int, int | None, float]:
    """Parse '1-6', '0-99', or '35+' into (low, high, points)."""
    tier = str(tier).strip()
    if tier.endswith("+"):
        return int(tier[:-1]), None, 0.0
    if "-" in tier:
        low, high = tier.split("-", 1)
        return int(low), int(high), 0.0
    return int(tier), int(tier), 0.0


def dst_tier_bonus(value: float, tiers: dict) -> float:
    """ESPN D/ST tier bonus for points_allowed or yards_allowed."""
    amount = int(round(float(value or 0)))
    for tier_key, pts in tiers.items():
        low, high, _ = _parse_dst_tier(str(tier_key))
        if high is None and amount >= low:
            return float(pts)
        if high is not None and low <= amount <= high:
            return float(pts)
    return 0.0


def points_allowed_bonus(points_allowed: float, tiers: dict) -> float:
    """ESPN points-allowed tier bonus from opponent score."""
    return dst_tier_bonus(points_allowed, tiers)


def compute_kicker_points(df: pd.DataFrame) -> pd.Series:
    """Weekly or season kicker fantasy points (ESPN)."""
    weights = load_kicker_preset()
    total = pd.Series(0.0, index=df.index)
    for stat, weight in weights.items():
        if stat in df.columns and weight != 0:
            total += pd.to_numeric(df[stat], errors="coerce").fillna(0) * weight
    return total.round(2)


_DST_TIER_STATS = ("points_allowed", "yards_allowed")


def compute_dst_points(df: pd.DataFrame) -> pd.Series:
    """Weekly or season team D/ST fantasy points (ESPN)."""
    preset = load_dst_preset()
    total = pd.Series(0.0, index=df.index)

    for stat, weight in preset.items():
        if stat in _DST_TIER_STATS:
            continue
        if stat in df.columns and weight != 0:
            total += pd.to_numeric(df[stat], errors="coerce").fillna(0) * float(weight)

    for stat in _DST_TIER_STATS:
        tiers = preset.get(stat, {})
        if stat in df.columns and tiers:
            total += df[stat].apply(lambda v, t=tiers: dst_tier_bonus(v, t))

    return total.round(2)


def apply_kicker_points(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[KICKER_FP_COLUMN] = compute_kicker_points(out)
    return out


def apply_dst_points(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[DST_FP_COLUMN] = compute_dst_points(out)
    return out
