"""Z-score variance analytics vs peers and career."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.positions import is_dst_position, positions_for_peer_grouping
from src.scoring.calc import fp_column_for_preset, resolve_preset
from src.settings import get_min_games_default

THRESHOLDS_PATH = Path(__file__).parent / "thresholds.yaml"


def load_thresholds() -> dict:
    with THRESHOLDS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_min_games(min_games: int | None = None) -> int:
    if min_games is not None:
        return min_games
    return get_min_games_default()


def _volume_column(position: str) -> tuple[str, float] | None:
    gates = load_thresholds()["volume_gates"]
    pos = positions_for_peer_grouping(position) or ""
    if pos in gates:
        gate = gates[pos]
        key = next(iter(gate))
        return key, float(gate[key])
    default = gates.get("default", {})
    if "games" in default:
        return "games", float(default["games"])
    return None


def qualifies_for_peer_z(
    row: pd.Series,
    thresholds: dict | None = None,
    min_games: int | None = None,
) -> bool:
    if is_dst_position(row.get("position")):
        return bool(row.get("games", 0) > 0)

    thresholds = thresholds or load_thresholds()
    games_min = get_min_games(min_games)
    if row.get("games", 0) < games_min:
        return False
    pos = row.get("position", "")
    gate = _volume_column(pos)
    if gate is None:
        return True
    col, minimum = gate
    if col == "games":
        return row.get("games", 0) >= minimum
    if col == "passing_attempts":
        return row.get("passing_attempts", 0) >= minimum
    return row.get(col, 0) >= minimum


def add_volume_flags(df: pd.DataFrame, min_games: int | None = None) -> pd.DataFrame:
    out = df.copy()
    if "position" in out.columns:
        out["position"] = out["position"].apply(
            lambda p: positions_for_peer_grouping(p) if p is not None else p
        )
    out["peer_qualified"] = out.apply(
        lambda r: qualifies_for_peer_z(r, min_games=min_games),
        axis=1,
    )
    return out


def compute_peer_z_era(
    all_seasons_df: pd.DataFrame,
    fp_col: str = "fantasy_points",
) -> pd.DataFrame:
    """Z-score vs all qualified season-rows for same position (historical baseline)."""
    thresholds = load_thresholds()
    min_peers = thresholds.get("min_qualified_peers", 10)
    out = all_seasons_df.copy()
    qualified = out[out["peer_qualified"]]

    era_stats = (
        qualified.groupby("position")[fp_col]
        .agg(["mean", "std", "count"])
        .rename(columns={"mean": "era_mean", "std": "era_std", "count": "era_n"})
    )
    out = out.merge(era_stats, on="position", how="left")
    out["peer_z_era"] = np.where(
        (out["era_n"] >= min_peers) & (out["era_std"] > 0),
        (out[fp_col] - out["era_mean"]) / out["era_std"],
        np.nan,
    )
    return out


def compute_career_z(
    player_seasons: pd.DataFrame,
    fp_col: str = "fantasy_points",
    min_games: int | None = None,
) -> pd.DataFrame:
    """
    Z-score each season vs the player's own career mean/std.

    Only seasons that pass min-games and position volume gates (same rules as
    peer Z) are included in the baseline and receive a career Z value.
    """
    out = add_volume_flags(player_seasons.copy(), min_games=min_games)
    out["career_z"] = np.nan

    qualified = out[out["peer_qualified"]]
    if len(qualified) < 2:
        return out

    mean = qualified[fp_col].mean()
    std = qualified[fp_col].std()
    if std == 0 or np.isnan(std):
        return out

    out.loc[qualified.index, "career_z"] = (qualified[fp_col] - mean) / std
    return out


def enrich_season_with_z_scores(
    conn,
    season: int,
    preset: str,
    include_era: bool = False,
    min_games: int | None = None,
    positions: list[str] | None = None,
) -> pd.DataFrame:
    """Build season leaderboard dataframe with Z columns (delegates to peer_z)."""
    from src.analytics.peer_z import enrich_leaders_dataframe
    from src.db.queries import season_leaders
    from src.positions import OFFENSE_POSITIONS

    mg = get_min_games(min_games)
    pos = positions or list(OFFENSE_POSITIONS)
    df = season_leaders(conn, season, preset, positions=pos, min_games=mg)
    if df.empty:
        return df
    df = enrich_leaders_dataframe(
        conn, df, season, preset, pos, mg, era_z=include_era
    )
    preset_key = resolve_preset(preset)
    fp_col = fp_column_for_preset(preset_key)
    return df.sort_values("fantasy_points" if "fantasy_points" in df.columns else fp_col, ascending=False)


__all__ = [
    "add_volume_flags",
    "compute_career_z",
    "compute_peer_z_era",
    "enrich_season_with_z_scores",
    "get_min_games",
    "load_thresholds",
    "qualifies_for_peer_z",
]
