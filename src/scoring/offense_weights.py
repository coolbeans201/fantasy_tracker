"""Offensive stat weights for built-in and custom scoring presets."""

from __future__ import annotations

# Stats available for custom offense scoring (subset of STAT_COLUMNS with preset weights)
OFFENSE_SCORING_STATS: tuple[str, ...] = (
    "passing_yards",
    "passing_tds",
    "interceptions",
    "rushing_yards",
    "rushing_tds",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "fumbles_lost",
)

_BUILTIN_CLONE_LABELS: dict[str, str] = {
    "standard": "Standard",
    "half_ppr": "Half-PPR",
    "full_ppr": "Full PPR",
}


def validate_offense_weights(weights: dict) -> dict[str, float]:
    """Return normalized offense weights; raise ValueError on unknown keys."""
    if not weights:
        raise ValueError("At least one offensive stat weight is required.")
    out: dict[str, float] = {}
    for key, val in weights.items():
        if key not in OFFENSE_SCORING_STATS:
            raise ValueError(f"Unknown scoring stat: {key}")
        out[key] = float(val)
    if not any(v != 0 for v in out.values()):
        raise ValueError("At least one non-zero weight is required.")
    return out


def offense_weights_from_builtin(preset_key: str) -> dict[str, float]:
    from src.scoring.calc import load_presets

    presets = load_presets()
    if preset_key not in presets:
        raise ValueError(f"Unknown built-in preset: {preset_key}")
    raw = presets[preset_key]
    return validate_offense_weights(
        {k: float(raw[k]) for k in OFFENSE_SCORING_STATS if k in raw}
    )


def compute_offense_fp_series(df, weights: dict[str, float]):
    """Pandas FP from offense weights (no kicker/DST)."""
    import pandas as pd

    total = pd.Series(0.0, index=df.index)
    for stat, weight in weights.items():
        if weight == 0:
            continue
        if stat not in df.columns:
            continue
        total += pd.to_numeric(df[stat], errors="coerce").fillna(0) * weight
    return total.round(2)


def offense_fp_sql_sum(weights: dict[str, float], prefix: str = "") -> str:
    """SQL expression for weighted sum of offensive stats."""
    p = f"{prefix}." if prefix else ""
    terms: list[str] = []
    for stat, weight in weights.items():
        if weight == 0:
            continue
        terms.append(f"COALESCE({p}{stat}, 0) * {float(weight)}")
    if not terms:
        return "0.0"
    inner = " + ".join(terms)
    return f"ROUND(({inner}), 2)"
