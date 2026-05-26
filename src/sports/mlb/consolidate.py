"""Collapse duplicate ingest rows; keep one row per player-season-position-team."""

from __future__ import annotations

import pandas as pd

from src.db.sport_schema import MLB_PLAYER_SEASON_COLUMNS
from src.sports.mlb.positions import is_pitcher_position
from src.sports.mlb.scoring import compute_hitter_fp, compute_pitcher_fp
from src.sports.mlb.teams import is_summary_team, normalize_mlb_team
from src.text_encoding import normalize_unicode_series

_MLB_SUM_COLS = (
    "games",
    "runs",
    "home_runs",
    "rbi",
    "stolen_bases",
    "walks",
    "strikeouts_bat",
    "wins",
    "strikeouts_pitch",
    "saves",
    "innings_pitched",
    "fantasy_points_espn",
)


def drop_redundant_summary_team_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Remove BRef combined rows (2TM, TOT) when the same player-season-position
    already has real team stints.
    """
    if frame.empty or "team" not in frame.columns:
        return frame
    out = frame.copy()
    out["team"] = out["team"].map(normalize_mlb_team)
    out["_summary"] = out["team"].map(is_summary_team)
    keys = ["player_id", "season", "position"]
    has_split = out.groupby(keys, dropna=False)["_summary"].transform(lambda s: (~s).any())
    return out[~(out["_summary"] & has_split)].drop(columns=["_summary"])


def consolidate_mlb_season_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (player_id, season, position, team).

    Multi-team players stay separate for season leaders / team filters.
    Two-way players still merge only duplicate keys for the same team.
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
    out["team"] = out["team"].map(normalize_mlb_team)
    out = drop_redundant_summary_team_rows(out)

    agg: dict[str, str] = {c: "sum" for c in _MLB_SUM_COLS if c in out.columns}
    agg["player_name"] = "first"
    if "batting_avg" in out.columns:
        agg["batting_avg"] = "mean"
    if "era" in out.columns:
        agg["era"] = "mean"
    if "whip" in out.columns:
        agg["whip"] = "mean"

    grouped = (
        out.groupby(["player_id", "season", "position", "team"], as_index=False)
        .agg(agg)
        .reset_index(drop=True)
    )
    if "player_name" in grouped.columns:
        grouped["player_name"] = normalize_unicode_series(grouped["player_name"])
    if "fantasy_points_espn" in grouped.columns:
        hit_mask = ~grouped["position"].map(is_pitcher_position)
        pit_mask = grouped["position"].map(is_pitcher_position)
        if hit_mask.any():
            grouped.loc[hit_mask, "fantasy_points_espn"] = compute_hitter_fp(
                grouped.loc[hit_mask]
            )
        if pit_mask.any():
            grouped.loc[pit_mask, "fantasy_points_espn"] = compute_pitcher_fp(
                grouped.loc[pit_mask]
            )
    grouped = grouped.drop_duplicates(
        subset=["player_id", "season", "position", "team"], keep="first"
    )
    return grouped[list(MLB_PLAYER_SEASON_COLUMNS)]
