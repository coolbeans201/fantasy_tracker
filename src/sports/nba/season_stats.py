"""Map LeagueDashPlayerStats API rows to season counting-stat totals."""

from __future__ import annotations

import pandas as pd

# LeagueDashPlayerStats per_mode_detailed for season ingest (counting stats must be Totals).
LEAGUE_DASH_PER_MODE = "Totals"

COUNTING_STAT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("PTS", "points"),
    ("REB", "rebounds"),
    ("AST", "assists"),
    ("STL", "steals"),
    ("BLK", "blocks"),
    ("TOV", "turnovers"),
    ("FG3M", "three_pointers"),
)


def _col(raw: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in raw.columns:
            return raw[name]
    return pd.Series([None] * len(raw), index=raw.index)


def counting_stats_from_league_dash(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Extract integer season totals from a LeagueDashPlayerStats frame.

    Expects ``per_mode_detailed=Totals`` so PTS/REB/etc. are already season sums.
    """
    games = pd.to_numeric(_col(raw, "GP"), errors="coerce").fillna(0).astype(int)
    out = pd.DataFrame(index=raw.index)
    out["games"] = games
    for api_col, db_col in COUNTING_STAT_COLUMNS:
        out[db_col] = (
            pd.to_numeric(_col(raw, api_col), errors="coerce").fillna(0).round().astype("int64")
        )
    return out
