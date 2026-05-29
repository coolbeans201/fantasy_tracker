"""UI helpers for draft / weekly ECR surprise."""

from __future__ import annotations

import streamlit as st

from src.analytics.surprise import format_surprise_caption, top_surprise_slices
from src.stats_columns import rename_stats_for_display
from src.ui_text import bold_heading, title_case_ui


def render_surprise_highlights(
    surprise_df,
    *,
    season: int,
    position_label: str | None = None,
    caption: str | None = None,
) -> None:
    """Top outperformers and underperformers for a season."""
    if surprise_df is None or surprise_df.empty:
        return

    over, under = top_surprise_slices(surprise_df, n=10)
    pos_note = f" ({position_label})" if position_label else ""
    st.markdown(bold_heading(f"Beat draft rank — top 10{pos_note}"))
    if over.empty:
        st.caption("No qualified players with draft ECR for this filter.")
    else:
        cols = ["player_name", "position", "draft_ecr", "finish_rank", "rank_delta"]
        cols = [c for c in cols if c in over.columns]
        st.dataframe(
            rename_stats_for_display(over[cols]),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(bold_heading(f"Missed draft rank — bottom 10{pos_note}"))
    if under.empty:
        st.caption("No qualified players with draft ECR for this filter.")
    else:
        cols = ["player_name", "position", "draft_ecr", "finish_rank", "rank_delta"]
        cols = [c for c in cols if c in under.columns]
        st.dataframe(
            rename_stats_for_display(under[cols]),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(caption or format_surprise_caption())


def render_surprise_metrics_row(metrics: dict | None) -> None:
    """Profile season-detail metrics for one player."""
    if not metrics:
        return
    st.caption(
        f"Draft ECR **{metrics['draft_ecr']}** · finish **{metrics['finish_rank']}** · "
        f"rank Δ **{metrics['rank_delta']:+d}** "
        "(positive = finished better than preseason rank)"
    )
