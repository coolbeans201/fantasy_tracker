"""ESPN-style NBA points (v1)."""

from __future__ import annotations

import pandas as pd

WEIGHTS = {
    "points": 1.0,
    "rebounds": 1.2,
    "assists": 1.5,
    "steals": 3.0,
    "blocks": 3.0,
    "turnovers": -1.0,
    "three_pointers": 0.5,
}


def compute_fp(df: pd.DataFrame) -> pd.Series:
    total = pd.Series(0.0, index=df.index)
    for col, w in WEIGHTS.items():
        if col in df.columns:
            total += pd.to_numeric(df[col], errors="coerce").fillna(0) * w
    return total.round(2)
