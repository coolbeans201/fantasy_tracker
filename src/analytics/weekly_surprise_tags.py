"""Rank-delta boom/bust tags for weekly ECR surprise (non-NFL sports)."""

from __future__ import annotations

import pandas as pd

from src.analytics.variance import load_thresholds


def position_week_rank_delta_percentiles(
    surprise_df: pd.DataFrame,
    *,
    min_peers: int | None = None,
) -> tuple[float | None, float | None]:
    """P25/P75 of rank_delta among qualified player-weeks for one position-week cohort."""
    if surprise_df.empty or "rank_delta" not in surprise_df.columns:
        return None, None
    min_peers = min_peers or int(load_thresholds().get("min_qualified_peers", 10))
    qualified = surprise_df[surprise_df.get("week_qualified", True) == True]  # noqa: E712
    deltas = pd.to_numeric(qualified["rank_delta"], errors="coerce").dropna()
    if len(deltas) < min_peers:
        return None, None
    return float(deltas.quantile(0.25)), float(deltas.quantile(0.75))


def week_rank_surprise_tags(
    weekly_df: pd.DataFrame,
    *,
    p25: float | None,
    p75: float | None,
    beat_label: str = "Beat rank",
    miss_label: str = "Missed rank",
) -> pd.Series:
    """Tag weeks where rank_delta is in the top/bottom quartile of the cohort."""
    if weekly_df.empty or "rank_delta" not in weekly_df.columns:
        return pd.Series([""] * len(weekly_df), index=weekly_df.index)
    if p25 is None or p75 is None:
        return pd.Series([""] * len(weekly_df), index=weekly_df.index)

    tags: list[str] = []
    for _idx, row in weekly_df.iterrows():
        delta = row.get("rank_delta")
        if delta is None or (isinstance(delta, float) and pd.isna(delta)):
            tags.append("")
            continue
        d = float(delta)
        if d >= p75:
            tags.append(beat_label)
        elif d <= p25:
            tags.append(miss_label)
        else:
            tags.append("")
    return pd.Series(tags, index=weekly_df.index)


def rank_surprise_rates(
    weekly_df: pd.DataFrame,
    *,
    p25: float | None,
    p75: float | None,
) -> dict[str, float | None]:
    tags = week_rank_surprise_tags(weekly_df, p25=p25, p75=p75)
    tagged = tags[tags != ""]
    n = len(weekly_df)
    if n == 0:
        return {"beat_rate": None, "miss_rate": None}
    beat = float((tags == "Beat rank").sum()) / n
    miss = float((tags == "Missed rank").sum()) / n
    return {"beat_rate": beat, "miss_rate": miss, "tagged_weeks": len(tagged)}


def format_sport_weekly_surprise_caption(
    p25: float | None,
    p75: float | None,
    *,
    sport_id: str,
    position_label: str | None = None,
) -> str:
    from src.sports.registry import get_sport

    label = get_sport(sport_id).label
    pos = f" for {position_label}" if position_label else ""
    if p25 is None or p75 is None:
        return (
            f"Weekly beat/miss tags unavailable{pos} (need enough qualified player-weeks)."
        )
    return (
        f"Weekly **beat/miss** vs P25/P75 of rank Δ (weekly ECR − finish rank) among "
        f"volume-qualified {label} player-weeks{pos}: "
        f"**beat** ≥ **{p75:+.0f}** spots, **miss** ≤ **{p25:+.0f}** spots. "
        "FantasyPros week index may differ from calendar Mon–Sun buckets shown in FP column."
    )
