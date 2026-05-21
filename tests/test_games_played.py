"""Games played derived from weekly rows."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ingest_season import build_aggregates  # noqa: E402
from src.stats_columns import FANTASY_POINT_COLUMNS, STAT_COLUMNS  # noqa: E402


def _weekly_frame() -> pd.DataFrame:
    base = {
        "player_id": ["p1", "p1", "p1"],
        "player_name": ["Player One"] * 3,
        "season": [2024, 2024, 2024],
        "week": [1, 2, 3],
        "season_type": ["REG", "REG", "REG"],
        "team": ["NYG", "NYG", "NYG"],
        "position": ["RB", "RB", "RB"],
    }
    for col in STAT_COLUMNS:
        base[col] = 0
    for col in FANTASY_POINT_COLUMNS:
        base[col] = [1.0, 2.0, 3.0]
    return pd.DataFrame(base)


def test_season_games_is_distinct_weeks():
    _, season, _ = build_aggregates(_weekly_frame())
    assert len(season) == 1
    assert int(season.iloc[0]["games"]) == 3
