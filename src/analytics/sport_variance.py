"""Volume gates and career Z for MLB / NBA / NHL."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.variance import load_thresholds
from src.sports.peer_positions import positions_for_peer_grouping
from src.settings import get_min_games_default


def _sport_volume_gates(sport_id: str) -> dict:
    raw = load_thresholds()
    by_sport = raw.get("volume_gates_by_sport") or {}
    return dict(by_sport.get(str(sport_id).strip().lower(), {}))


def _volume_column_sport(sport_id: str, position: str | None) -> tuple[str, float] | None:
    gates = _sport_volume_gates(sport_id)
    pos = positions_for_peer_grouping(sport_id, position) or ""
    if pos in gates:
        gate = gates[pos]
        key = next(iter(gate))
        return key, float(gate[key])
    default = gates.get("default", {})
    if "games" in default:
        return "games", float(default["games"])
    return None


def qualifies_for_peer_z_sport(
    row: pd.Series,
    sport_id: str,
    *,
    min_games: int | None = None,
) -> bool:
    games_min = min_games if min_games is not None else get_min_games_default()
    if float(row.get("games", 0) or 0) < games_min:
        return False
    gate = _volume_column_sport(sport_id, row.get("position"))
    if gate is None:
        return True
    col, minimum = gate
    return float(row.get(col, 0) or 0) >= minimum


def add_volume_flags_sport(
    df: pd.DataFrame,
    sport_id: str,
    min_games: int | None = None,
) -> pd.DataFrame:
    out = df.copy()
    if "position" in out.columns:
        out["position"] = out["position"].apply(
            lambda p: positions_for_peer_grouping(sport_id, p) if p is not None else p
        )
    out["peer_qualified"] = out.apply(
        lambda r: qualifies_for_peer_z_sport(r, sport_id, min_games=min_games),
        axis=1,
    )
    return out


def compute_career_z_sport(
    player_seasons: pd.DataFrame,
    sport_id: str,
    fp_col: str = "fantasy_points",
    min_games: int | None = None,
) -> pd.DataFrame:
    """Z-score each season vs the player's own qualified career baseline."""
    out = add_volume_flags_sport(player_seasons.copy(), sport_id, min_games=min_games)
    out["career_z"] = np.nan
    qualified = out[out["peer_qualified"]]
    if str(sport_id).strip().lower() == "mlb" and "season" in qualified.columns:
        from src.sports.mlb.seasons import mlb_career_z_excluded_season

        baseline_mask = ~qualified["season"].map(mlb_career_z_excluded_season)
        qualified = qualified[baseline_mask]
    if len(qualified) < 2:
        return out
    mean = qualified[fp_col].mean()
    std = qualified[fp_col].std()
    if std == 0 or np.isnan(std):
        return out
    assign_mask = out["peer_qualified"]
    if str(sport_id).strip().lower() == "mlb" and "season" in out.columns:
        from src.sports.mlb.seasons import mlb_career_z_excluded_season

        assign_mask = assign_mask & ~out["season"].map(mlb_career_z_excluded_season)
    out.loc[assign_mask, "career_z"] = (
        out.loc[assign_mask, fp_col] - mean
    ) / std
    return out
