"""Streamlit UI for weekly consistency / boom-bust metrics."""

from __future__ import annotations

import streamlit as st

from src.ui_text import section_h3


def render_consistency_panel(
    metrics: dict[str, float | int | None],
    *,
    season: int,
    position_label: str | None = None,
    heading: str | None = None,
) -> None:
    """Prominent weekly σ and boom/bust metrics (Player Profile / Compare)."""
    pos_note = f" ({position_label})" if position_label else ""
    title = heading or f"Weekly consistency ({season})"
    st.markdown(section_h3(title))

    std = metrics.get("weekly_std")
    boom = metrics.get("boom_rate")
    bust = metrics.get("bust_rate")
    worst = metrics.get("worst_week_fp")
    weeks = metrics.get("weeks_played", 0)

    if std is None and boom is None and bust is None:
        st.info("Not enough weekly data to compute consistency metrics for this season.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "Weekly σ",
        f"{std:.1f}" if std is not None else "—",
        help=(
            "Standard deviation of weekly fantasy points. "
            "Lower values usually mean a steadier week-to-week floor."
        ),
    )
    c2.metric(
        "Boom rate",
        f"{boom * 100:.0f}%" if boom is not None else "—",
        help=(
            "Share of weeks at or above the 75th-percentile weekly FP "
            f"for this position{pos_note} in {season}."
        ),
    )
    c3.metric(
        "Bust rate",
        f"{bust * 100:.0f}%" if bust is not None else "—",
        help=(
            "Share of weeks at or below the 25th-percentile weekly FP "
            f"for this position{pos_note} in {season}."
        ),
    )
    c4.metric(
        "Worst week",
        f"{worst:.1f}" if worst is not None else "—",
        help="Lowest single-week fantasy point total in the regular season.",
    )
    c5.metric(
        "Weeks",
        str(weeks) if weeks else "—",
        help="Regular-season weeks with stored weekly stats.",
    )

    st.caption(
        "Boom and bust thresholds come from the same-season weekly distribution "
        f"for {position_label or 'this position'} — not from the sidebar scoring preset alone."
    )
