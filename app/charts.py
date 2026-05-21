"""Charts that avoid Streamlit's Altair dependency (Python 3.12 compatibility)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


def season_fantasy_points_chart(
    seasons_df: pd.DataFrame,
    *,
    y_column: str = "fantasy_points",
    y_label: str = "Fantasy Points",
) -> None:
    """Line chart of fantasy points by season (matplotlib, no Altair)."""
    plot_df = seasons_df.sort_values("season")
    if plot_df.empty or y_column not in plot_df.columns:
        st.caption("No chart data.")
        return

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(
        plot_df["season"],
        plot_df[y_column],
        marker="o",
        linewidth=2,
        color="#3366cc",
    )
    ax.set_xlabel("Season")
    ax.set_ylabel(y_label)
    ax.set_xticks(plot_df["season"])
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)
