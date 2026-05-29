"""Per-game boom/bust vs a player's own season fantasy-point distribution."""

from __future__ import annotations

import pandas as pd


def player_game_fp_percentiles(
    games_df: pd.DataFrame,
    *,
    fp_col: str = "fantasy_points",
    min_games: int = 4,
) -> tuple[float | None, float | None]:
    """
    P25/P75 of fantasy points across games in the loaded log.

    Uses the player's own games (not league peers) so two-way players are judged
  against their role-specific game log shown on the profile.
    """
    if games_df.empty or fp_col not in games_df.columns:
        return None, None
    values = pd.to_numeric(games_df[fp_col], errors="coerce").dropna()
    if len(values) < min_games:
        return None, None
    return float(values.quantile(0.25)), float(values.quantile(0.75))


def game_boom_bust_tags(
    games_df: pd.DataFrame,
    *,
    p25: float | None = None,
    p75: float | None = None,
    fp_col: str = "fantasy_points",
) -> pd.Series:
    """Strong game = FP >= player P75; weak game = FP <= player P25."""
    if games_df.empty or fp_col not in games_df.columns:
        return pd.Series(dtype=str)

    if p25 is None or p75 is None or p25 >= p75:
        return pd.Series([""] * len(games_df), index=games_df.index)

    fp = pd.to_numeric(games_df[fp_col], errors="coerce")
    tags: list[str] = []
    for value in fp:
        if pd.isna(value):
            tags.append("")
        elif value >= p75:
            tags.append("Strong")
        elif value <= p25:
            tags.append("Weak")
        else:
            tags.append("")
    return pd.Series(tags, index=games_df.index)


def consistency_from_games(
    games_df: pd.DataFrame,
    *,
    p25: float | None = None,
    p75: float | None = None,
    fp_col: str = "fantasy_points",
) -> dict[str, float | int | None]:
    """Game-level shape metrics (player-relative boom/bust rates)."""
    if games_df.empty or fp_col not in games_df.columns:
        return {
            "game_std": None,
            "boom_rate": None,
            "bust_rate": None,
            "games_played": 0,
            "worst_game_fp": None,
        }

    fp = pd.to_numeric(games_df[fp_col], errors="coerce").dropna()
    if fp.empty:
        return {
            "game_std": None,
            "boom_rate": None,
            "bust_rate": None,
            "games_played": 0,
            "worst_game_fp": None,
        }

    std = float(fp.std()) if len(fp) > 1 else 0.0
    boom = bust = None
    if p75 is not None:
        boom = float((fp >= p75).mean())
    if p25 is not None:
        bust = float((fp <= p25).mean())

    return {
        "game_std": std,
        "boom_rate": boom,
        "bust_rate": bust,
        "games_played": int(len(fp)),
        "worst_game_fp": float(fp.min()),
    }


def format_game_boom_bust_caption(
    p25: float | None,
    p75: float | None,
    *,
    game_unit: str = "game",
) -> str:
    if p25 is None or p75 is None:
        return (
            f"Need at least **4** {game_unit}s to highlight strong/weak outings "
            f"vs this player's season distribution."
        )
    return (
        f"**Strong** {game_unit}s (green) = FP ≥ **{p75:.1f}** (player's top quartile). "
        f"**Weak** {game_unit}s (red) = FP ≤ **{p25:.1f}** (bottom quartile). "
        f"Thresholds are based on **this player's** {game_unit}s only, not league peers."
    )
