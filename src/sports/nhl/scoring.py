"""ESPN-style NHL points (v1) — skater vs goalie."""

from __future__ import annotations

import pandas as pd

SKATER_WEIGHTS = {
    "goals": 3.0,
    "assists": 2.0,
    "shots": 0.5,
    "blocks": 0.5,
    "hits": 0.25,
}

GOALIE_WEIGHTS = {
    "wins": 4.0,
    "saves": 0.2,
    "goals_against": -1.0,
    "shutouts": 3.0,
}


def compute_skater_fp(df: pd.DataFrame) -> pd.Series:
    total = pd.Series(0.0, index=df.index)
    for col, w in SKATER_WEIGHTS.items():
        if col in df.columns:
            total += pd.to_numeric(df[col], errors="coerce").fillna(0) * w
    return total.round(2)


def compute_goalie_fp(df: pd.DataFrame) -> pd.Series:
    total = pd.Series(0.0, index=df.index)
    for col, w in GOALIE_WEIGHTS.items():
        if col in df.columns:
            total += pd.to_numeric(df[col], errors="coerce").fillna(0) * w
    return total.round(2)
