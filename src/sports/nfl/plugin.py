"""NFL plugin metadata."""

from __future__ import annotations

from dataclasses import dataclass

SPORT_ID = "nfl"
WEEKLY_TABLE = "weekly_stats"
SEASON_TABLE = "season_stats"
GAME_NUMBER_COLUMN = "week"


@dataclass(frozen=True)
class NflPlugin:
    sport_id: str = SPORT_ID
    weekly_table: str = WEEKLY_TABLE
    season_table: str = SEASON_TABLE
    game_column: str = GAME_NUMBER_COLUMN


NFL_PLUGIN = NflPlugin()
