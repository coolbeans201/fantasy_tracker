"""Charts that avoid Streamlit's Altair dependency (Python 3.12 compatibility)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


def _season_chart_layout(n_seasons: int, *, dense: bool) -> tuple[float, float, int, bool]:
    """Figure size, x-label step, and whether to use compact markers."""
    use_dense = dense or n_seasons >= 15
    if not use_dense:
        return 10.0, 3.5, 1, True

    width = max(12.0, min(n_seasons * 0.45, 32.0))
    height = 4.25
    if n_seasons > 24:
        step = 5
    elif n_seasons > 18:
        step = 3
    else:
        step = 2
    show_markers = n_seasons <= 20
    return width, height, step, show_markers


def season_fantasy_points_chart(
    seasons_df: pd.DataFrame,
    *,
    y_column: str = "fantasy_points",
    y_label: str = "Fantasy Points",
    dense: bool = False,
) -> None:
    """Line chart of fantasy points by season (matplotlib, no Altair)."""
    plot_df = seasons_df.sort_values("season")
    if plot_df.empty or y_column not in plot_df.columns:
        st.caption("No chart data.")
        return

    n = len(plot_df)
    width, height, tick_step, show_markers = _season_chart_layout(n, dense=dense)
    seasons = plot_df["season"].astype(int)

    fig, ax = plt.subplots(figsize=(width, height))
    ax.plot(
        seasons,
        plot_df[y_column],
        marker="o" if show_markers else None,
        markersize=4 if show_markers else 0,
        linewidth=2,
        color="#3366cc",
    )
    ax.set_xlabel("Season")
    ax.set_ylabel(y_label)

    tick_seasons = seasons.iloc[::tick_step] if tick_step > 1 else seasons
    ax.set_xticks(tick_seasons)
    if tick_step > 1 or dense or n >= 15:
        ax.tick_params(axis="x", rotation=45)
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")

    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)
