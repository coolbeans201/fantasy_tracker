"""ESPN-style MLB points (v1) — simplified season totals."""

from __future__ import annotations

import pandas as pd

# Hitter: R, HR, RBI, SB, BB, K (bat), AVG not in linear v1
HITTER_WEIGHTS = {
    "runs": 1.0,
    "home_runs": 4.0,
    "rbi": 1.0,
    "stolen_bases": 2.0,
    "walks": 1.0,
    "strikeouts_bat": -0.5,
}

PITCHER_WEIGHTS = {
    "wins": 5.0,
    "strikeouts_pitch": 1.0,
    "saves": 5.0,
    "innings_pitched": 3.0,
    "era": -1.0,  # rough linear proxy; real leagues use categories
}


def compute_hitter_fp(df: pd.DataFrame) -> pd.Series:
    total = pd.Series(0.0, index=df.index)
    for col, w in HITTER_WEIGHTS.items():
        if col in df.columns:
            total += pd.to_numeric(df[col], errors="coerce").fillna(0) * w
    return total.round(2)


def compute_pitcher_fp(df: pd.DataFrame) -> pd.Series:
    total = pd.Series(0.0, index=df.index)
    for col, w in PITCHER_WEIGHTS.items():
        if col in df.columns:
            total += pd.to_numeric(df[col], errors="coerce").fillna(0) * w
    return total.round(2)
