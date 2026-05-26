"""Collapse duplicate ingest rows; keep one row per player-season-position-team."""

from __future__ import annotations

import pandas as pd

from src.db.sport_schema import NHL_PLAYER_SEASON_COLUMNS
from src.sports.nhl.positions import is_goalie_position
from src.sports.nhl.scoring import compute_goalie_fp, compute_skater_fp
from src.sports.nhl.teams import (
    is_combined_team_label,
    is_summary_team,
    normalize_nhl_team,
)
from src.text_encoding import normalize_unicode_series

_NHL_SUM_COLS = (
    "games",
    "goals",
    "assists",
    "points",
    "plus_minus",
    "shots",
    "hits",
    "blocks",
    "wins",
    "saves",
    "goals_against",
    "shutouts",
    "fantasy_points_espn",
)


def drop_redundant_combined_team_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Drop combined team labels (TOT, TOR,EDM) when per-team stints already exist.
    """
    if frame.empty or "team" not in frame.columns:
        return frame
    out = frame.copy()
    out["team"] = out["team"].map(normalize_nhl_team)
    out["_combined"] = out["team"].map(
        lambda t: is_combined_team_label(t) or is_summary_team(t)
    )
    keys = ["player_id", "season", "position"]
    has_split = out.groupby(keys, dropna=False)["_combined"].transform(lambda s: (~s).any())
    return out[~(out["_combined"] & has_split)].drop(columns=["_combined"])


def consolidate_nhl_season_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (player_id, season, position, team).

    Mid-season trades from the NHL stats API stay as separate rows.
    """
    if frame.empty:
        return frame
    out = frame.copy()
    out["player_id"] = (
        out["player_id"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )
    out["position"] = out["position"].astype(str).str.strip().str.upper()
    out["team"] = out["team"].map(normalize_nhl_team)
    out = drop_redundant_combined_team_rows(out)

    agg: dict[str, str] = {c: "sum" for c in _NHL_SUM_COLS if c in out.columns}
    agg["player_name"] = "first"

    grouped = (
        out.groupby(["player_id", "season", "position", "team"], as_index=False)
        .agg(agg)
        .reset_index(drop=True)
    )
    if "player_name" in grouped.columns:
        grouped["player_name"] = normalize_unicode_series(grouped["player_name"])
    if "fantasy_points_espn" in grouped.columns:
        skater_mask = ~grouped["position"].map(is_goalie_position)
        goalie_mask = grouped["position"].map(is_goalie_position)
        if skater_mask.any():
            grouped.loc[skater_mask, "fantasy_points_espn"] = compute_skater_fp(
                grouped.loc[skater_mask]
            )
        if goalie_mask.any():
            grouped.loc[goalie_mask, "fantasy_points_espn"] = compute_goalie_fp(
                grouped.loc[goalie_mask]
            )
    grouped = grouped.drop_duplicates(
        subset=["player_id", "season", "position", "team"], keep="first"
    )
    return grouped[list(NHL_PLAYER_SEASON_COLUMNS)]
