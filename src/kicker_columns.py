"""Kicker stat columns and nflverse name mapping."""

from __future__ import annotations

KICKER_STAT_COLUMNS = [
    "pat_made",
    "pat_missed",
    "fg_missed",
    "fg_made_0_19",
    "fg_made_20_29",
    "fg_made_30_39",
    "fg_made_40_49",
    "fg_made_50_59",
    "fg_made_60_",
]

# nflverse player stats -> schema (first match wins per target column)
NFLVERSE_KICKER_MAP: dict[str, str] = {
    "pat_made": "pat_made",
    "xp_made": "pat_made",
    "pat_missed": "pat_missed",
    "xp_missed": "pat_missed",
    "fg_missed": "fg_missed",
    "fg_made_0_19": "fg_made_0_19",
    "fg_made_19": "fg_made_0_19",
    "fg_made_20_29": "fg_made_20_29",
    "fg_made_29": "fg_made_20_29",
    "fg_made_30_39": "fg_made_30_39",
    "fg_made_39": "fg_made_30_39",
    "fg_made_40_49": "fg_made_40_49",
    "fg_made_49": "fg_made_40_49",
    "fg_made_50_59": "fg_made_50_59",
    "fg_made_50": "fg_made_50_59",
    "fg_made_60_": "fg_made_60_",
    "fg_made_60": "fg_made_60_",
}
