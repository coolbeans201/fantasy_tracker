"""Weekly consistency and boom/bust rates from game-level fantasy points."""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from src.analytics.variance import qualifies_weekly_volume
from src.positions import DST_POSITION, is_dst_position, positions_for_peer_grouping
from src.scoring.calc import fantasy_points_sql_expr, resolve_preset
from src.scoring.special import DST_FP_COLUMN, KICKER_FP_COLUMN

_WEEKLY_VOLUME_COLS = (
    "position",
    "passing_attempts",
    "carries",
    "targets",
    "receptions",
)


def _weekly_fp_sql(preset: str, position: str | None) -> str:
    if is_dst_position(position):
        return DST_FP_COLUMN
    if positions_for_peer_grouping(position) == "K":
        return KICKER_FP_COLUMN
    return fantasy_points_sql_expr(preset)


def _filter_qualified_weekly_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep player-weeks that meet per-week volume gates (offense/K) or all DST weeks."""
    if df.empty:
        return df
    work = df.copy()
    if "position" in work.columns:
        work.columns = [str(c).strip().lower() for c in work.columns]
    mask = work.apply(qualifies_weekly_volume, axis=1)
    return work.loc[mask]


def position_weekly_percentiles(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    position: str | None,
    preset: str,
) -> tuple[float | None, float | None]:
    """
    P25 and P75 weekly fantasy points for a position in one season.

    Cohort = regular-season player-weeks (or team-weeks for DST) that pass per-week
    volume gates aligned with peer Z thresholds (season gate / 17 weeks).
    """
    pos = positions_for_peer_grouping(position)
    if not pos:
        return None, None

    if pos == DST_POSITION:
        sql = f"""
            SELECT {DST_FP_COLUMN} AS fp, '{DST_POSITION}' AS position
            FROM team_defense_weekly
            WHERE season = ? AND season_type = 'REG'
        """
        params: list = [season]
    else:
        fp_expr = _weekly_fp_sql(preset, pos)
        vol = ", ".join(c for c in _WEEKLY_VOLUME_COLS if c != "position")
        sql = f"""
            SELECT {fp_expr} AS fp, position, {vol}
            FROM weekly_stats
            WHERE season = ? AND season_type = 'REG' AND position = ?
        """
        params = [season, pos]

    df = conn.execute(sql, params).df()
    if df.empty:
        return None, None
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "fp" not in df.columns:
        return None, None

    qualified = _filter_qualified_weekly_rows(df)
    values = pd.to_numeric(qualified["fp"], errors="coerce").dropna()
    if len(values) < 4:
        return None, None
    return float(values.quantile(0.25)), float(values.quantile(0.75))


def consistency_from_weekly(
    weekly_df: pd.DataFrame,
    *,
    p25: float | None = None,
    p75: float | None = None,
    fp_col: str = "fantasy_points",
) -> dict[str, float | int | None]:
    """
    Weekly shape metrics for one entity-season.

    Boom = share of weeks with FP >= qualified peer-week P75 for that position-season.
    Bust = share of weeks with FP <= qualified peer-week P25.
    """
    if weekly_df.empty or fp_col not in weekly_df.columns:
        return {
            "weekly_std": None,
            "boom_rate": None,
            "bust_rate": None,
            "weeks_played": 0,
            "worst_week_fp": None,
        }

    fp = pd.to_numeric(weekly_df[fp_col], errors="coerce").dropna()
    if fp.empty:
        return {
            "weekly_std": None,
            "boom_rate": None,
            "bust_rate": None,
            "weeks_played": 0,
            "worst_week_fp": None,
        }

    std = float(fp.std()) if len(fp) > 1 else 0.0
    boom = bust = None
    if p75 is not None:
        boom = float((fp >= p75).mean())
    if p25 is not None:
        bust = float((fp <= p25).mean())

    return {
        "weekly_std": std,
        "boom_rate": boom,
        "bust_rate": bust,
        "weeks_played": int(len(fp)),
        "worst_week_fp": float(fp.min()),
    }


def week_boom_bust_tags(
    weekly_df: pd.DataFrame,
    *,
    p25: float | None = None,
    p75: float | None = None,
    fp_col: str = "fantasy_points",
) -> pd.Series:
    """
    Per-week labels from position-season P25/P75 thresholds.

    Boom = FP >= P75; bust = FP <= P25. Middle weeks are unlabeled.
    """
    if weekly_df.empty or fp_col not in weekly_df.columns:
        return pd.Series(dtype=str)

    if p25 is None or p75 is None or p25 >= p75:
        return pd.Series([""] * len(weekly_df), index=weekly_df.index)

    fp = pd.to_numeric(weekly_df[fp_col], errors="coerce")
    tags: list[str] = []
    for value in fp:
        if pd.isna(value):
            tags.append("")
        elif value >= p75:
            tags.append("Boom")
        elif value <= p25:
            tags.append("Bust")
        else:
            tags.append("")
    return pd.Series(tags, index=weekly_df.index)


def format_weekly_boom_bust_caption(
    p25: float | None,
    p75: float | None,
    *,
    position_label: str | None = None,
) -> str:
    pos = f" for {position_label}" if position_label else ""
    if p25 is None or p75 is None:
        return f"Weekly boom/bust thresholds unavailable{pos} (need enough peer weeks)."
    return (
        f"Boom/bust vs P25/P75 of **volume-qualified** player-weeks{pos} in this season "
        f"(same carries/attempts/targets gates as peer Z, prorated per week): "
        f"**boom** ≥ **{p75:.1f}** FP (green), **bust** ≤ **{p25:.1f}** FP (red)."
    )


def format_consistency_caption(metrics: dict[str, float | int | None]) -> str:
    parts: list[str] = []
    if metrics.get("weekly_std") is not None:
        parts.append(f"weekly σ {metrics['weekly_std']:.1f}")
    if metrics.get("boom_rate") is not None:
        parts.append(f"boom {metrics['boom_rate'] * 100:.0f}%")
    if metrics.get("bust_rate") is not None:
        parts.append(f"bust {metrics['bust_rate'] * 100:.0f}%")
    return " · ".join(parts) if parts else "Insufficient weekly data for consistency metrics."
