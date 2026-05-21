"""Season volume distributions for cross-checking peer-Z gates."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.analytics.variance import get_min_games, load_thresholds
from src.positions import FANTASY_POSITIONS, normalize_fantasy_position
from src.scoring.calc import fp_column_for_preset, resolve_preset


def volume_metric_for_position(position: str) -> str | None:
    """Return the volume stat column used for peer-Z gates."""
    pos = normalize_fantasy_position(position)
    if not pos:
        return None
    gates = load_thresholds().get("volume_gates", {})
    gate = gates.get(pos)
    if not gate:
        return None
    return next(iter(gate.keys()))


def volume_threshold_for_position(position: str) -> float | None:
    pos = normalize_fantasy_position(position)
    if not pos:
        return None
    gates = load_thresholds().get("volume_gates", {})
    gate = gates.get(pos)
    if not gate:
        return None
    return float(next(iter(gate.values())))


def load_season_volume_rows(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    min_games: int | None = None,
    preset: str = "Half-PPR",
) -> pd.DataFrame:
    """Season-level player rows with games and all volume-related columns."""
    min_games = get_min_games(min_games)
    fp_col = fp_column_for_preset(resolve_preset(preset))
    return conn.execute(
        f"""
        SELECT
            player_id,
            player_name,
            position,
            teams,
            games,
            {fp_col} AS fantasy_points,
            passing_attempts,
            carries,
            targets,
            receptions,
            passing_yards,
            rushing_yards,
            receiving_yards
        FROM season_stats
        WHERE season = ?
          AND games >= ?
          AND position IS NOT NULL
        ORDER BY position, player_name
        """,
        [season, min_games],
    ).df()


def summarize_position_volume(
    df: pd.DataFrame,
    position: str,
) -> dict | None:
    """Percentiles and qualification counts for one position's volume metric."""
    metric = volume_metric_for_position(position)
    threshold = volume_threshold_for_position(position)
    if not metric or threshold is None:
        return None

    pos = normalize_fantasy_position(position)
    subset = df[df["position"].apply(normalize_fantasy_position) == pos].copy()
    if subset.empty:
        return None

    values = subset[metric].fillna(0)
    qualified = (values >= threshold).sum()

    return {
        "position": pos,
        "metric": metric,
        "threshold": threshold,
        "n_players": len(subset),
        "n_qualified": int(qualified),
        "pct_qualified": round(100 * qualified / len(subset), 1) if len(subset) else 0,
        "min": float(values.min()),
        "p25": float(values.quantile(0.25)),
        "median": float(values.median()),
        "p75": float(values.quantile(0.75)),
        "max": float(values.max()),
        "mean": float(values.mean()),
    }


def build_volume_summary_table(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    min_games: int | None = None,
    preset: str = "Half-PPR",
) -> pd.DataFrame:
    """One row per fantasy position with distribution stats."""
    df = load_season_volume_rows(conn, season, min_games=min_games, preset=preset)
    rows = []
    for pos in FANTASY_POSITIONS:
        summary = summarize_position_volume(df, pos)
        if summary:
            rows.append(summary)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def rank_players_by_volume(
    df: pd.DataFrame,
    position: str,
    metric: str | None = None,
) -> pd.DataFrame:
    """Players at a position sorted by volume metric (desc)."""
    pos = normalize_fantasy_position(position)
    metric = metric or volume_metric_for_position(pos)
    if not metric:
        return pd.DataFrame()

    subset = df[df["position"].apply(normalize_fantasy_position) == pos].copy()
    cols = ["player_name", "teams", "games", metric, "fantasy_points", "receptions"]
    if metric == "receptions":
        cols = ["player_name", "teams", "games", metric, "targets", "fantasy_points"]
    elif metric == "targets":
        cols = ["player_name", "teams", "games", metric, "receptions", "fantasy_points"]
    elif metric == "passing_attempts":
        cols = ["player_name", "teams", "games", metric, "passing_yards", "fantasy_points"]
    elif metric == "carries":
        cols = ["player_name", "teams", "games", metric, "rushing_yards", "fantasy_points"]
    cols = [c for c in cols if c in subset.columns]
    return subset[cols].sort_values(metric, ascending=False).reset_index(drop=True)


def count_qualified_at_threshold(
    df: pd.DataFrame,
    position: str,
    metric: str,
    threshold: float,
) -> int:
    pos = normalize_fantasy_position(position)
    subset = df[df["position"].apply(normalize_fantasy_position) == pos]
    if subset.empty:
        return 0
    return int((subset[metric].fillna(0) >= threshold).sum())
