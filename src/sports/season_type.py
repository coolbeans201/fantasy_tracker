"""Regular-season filters for per-game ingest (exclude postseason / extras)."""

from __future__ import annotations

from typing import Any

import pandas as pd

# MLB statsapi game.gameType
MLB_REGULAR_GAME_TYPE = "R"

# NHL api-web path segment and nhlpy gameTypeId
NHL_REGULAR_GAME_TYPE_ID = 2


def is_mlb_regular_season_split(split: dict[str, Any]) -> bool:
    """True when a statsapi gameLog split is regular season."""
    if not isinstance(split, dict):
        return False
    game = split.get("game") or {}
    if not isinstance(game, dict):
        game = {}

    gt = game.get("gameType") or split.get("gameType")
    if gt is not None:
        return str(gt).strip().upper() == MLB_REGULAR_GAME_TYPE

    if game.get("isPostSeason") is True or split.get("isPostSeason") is True:
        return False
    season_type = str(split.get("seasonType") or game.get("seasonType") or "").strip().lower()
    if season_type in {"pst", "postseason", "playoffs", "playoff", "w"}:
        return False
    if season_type in {"reg", "regular", "r"}:
        return True
    # Spring / exhibition
    if season_type in {"spring", "springtraining", "st", "e", "exhibition"}:
        return False
    if str(game.get("gamedayType") or "").strip().lower() in {"s", "spring"}:
        return False
    return True


def filter_nba_gamelog_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Keep regular-season rows when NBA API exposes a season-type column."""
    if raw is None or raw.empty:
        return raw
    for col in raw.columns:
        if str(col).strip().lower() in ("season_type", "season_type_id"):
            series = raw[col].astype(str)
            mask = series.str.contains("Regular", case=False, na=False)
            return raw.loc[mask].copy()
    return raw


def filter_nhl_gamelog_games(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop non-regular games when gameType is present on NHL web API rows."""
    kept: list[dict[str, Any]] = []
    for row in games:
        if not isinstance(row, dict):
            continue
        gt = row.get("gameType") or row.get("gameTypeId") or row.get("game_type")
        if gt is None:
            kept.append(row)
            continue
        try:
            if int(gt) == NHL_REGULAR_GAME_TYPE_ID:
                kept.append(row)
        except (TypeError, ValueError):
            if str(gt).strip().lower() in {"2", "regular", "reg"}:
                kept.append(row)
    return kept
