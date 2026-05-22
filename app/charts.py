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
    peak_season: int | None = None,
    prime_seasons: list[int] | None = None,
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

    prime_set = set(prime_seasons or [])
    peak_yr = int(peak_season) if peak_season is not None else None
    drew_peak = False
    drew_prime = False
    drew_both = False
    for yr, fp in zip(seasons, plot_df[y_column]):
        yr_int = int(yr)
        is_peak = peak_yr is not None and yr_int == peak_yr
        is_prime = yr_int in prime_set

        if is_peak and is_prime:
            ax.scatter(
                [yr_int],
                [fp],
                s=160,
                facecolors="#ff9900",
                edgecolors="#2e7d32",
                linewidths=3,
                zorder=6,
                label="Peak + prime" if not drew_both else None,
            )
            drew_both = True
            continue
        if is_peak:
            ax.scatter(
                [yr_int],
                [fp],
                s=120,
                color="#ff9900",
                zorder=5,
                label="Peak season" if not drew_peak else None,
            )
            drew_peak = True
            continue
        if is_prime:
            ax.scatter(
                [yr_int],
                [fp],
                s=50,
                color="#22aa22",
                zorder=4,
                alpha=0.85,
                label="Prime (career Z > 1)" if not drew_prime else None,
            )
            drew_prime = True

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="best", fontsize=8)
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


def weekly_fantasy_points_chart(
    weekly_df: pd.DataFrame,
    *,
    y_column: str = "fantasy_points",
    y_label: str = "Fantasy Points",
    p25: float | None = None,
    p75: float | None = None,
) -> None:
    """Line chart of fantasy points by week with boom/bust week markers."""
    if weekly_df.empty or y_column not in weekly_df.columns:
        st.caption("No weekly chart data.")
        return

    plot_df = weekly_df.sort_values("week")
    weeks = plot_df["week"].astype(int)
    fp_vals = plot_df[y_column]

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(weeks, fp_vals, marker="o", markersize=5, linewidth=2, color="#3366cc", zorder=2)

    can_tag = p25 is not None and p75 is not None and p25 < p75
    drew_boom = drew_bust = False
    if can_tag:
        for week, fp in zip(weeks, fp_vals):
            if fp != fp:  # NaN
                continue
            if fp >= p75:
                ax.scatter(
                    [int(week)],
                    [fp],
                    s=90,
                    color="#43a047",
                    zorder=4,
                    label="Boom week" if not drew_boom else None,
                )
                drew_boom = True
            elif fp <= p25:
                ax.scatter(
                    [int(week)],
                    [fp],
                    s=90,
                    color="#e53935",
                    zorder=4,
                    label="Bust week" if not drew_bust else None,
                )
                drew_bust = True

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="best", fontsize=8)

    ax.set_xlabel("Week")
    ax.set_ylabel(y_label)
    ax.set_xticks(weeks)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def dual_entity_season_chart(
    merged: pd.DataFrame,
    name_a: str,
    name_b: str,
) -> None:
    """Overlay two entities' fantasy points by season (Compare all-time)."""
    if merged.empty:
        st.caption("No chart data.")
        return

    plot_df = merged.sort_values("season")
    seasons = plot_df["season"].astype(int)
    n = len(plot_df)
    width, height, tick_step, show_markers = _season_chart_layout(n, dense=n >= 15)

    fig, ax = plt.subplots(figsize=(width, height))
    for col, label, color in (
        ("fantasy_points_a", name_a, "#3366cc"),
        ("fantasy_points_b", name_b, "#dc3912"),
    ):
        if col not in plot_df.columns:
            continue
        ax.plot(
            seasons,
            plot_df[col],
            marker="o" if show_markers else None,
            markersize=4 if show_markers else 0,
            linewidth=2,
            label=label,
            color=color,
        )

    ax.set_xlabel("Season")
    ax.set_ylabel("Fantasy Points")
    tick_seasons = seasons.iloc[::tick_step] if tick_step > 1 else seasons
    ax.set_xticks(tick_seasons)
    if tick_step > 1 or n >= 15:
        ax.tick_params(axis="x", rotation=45)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)
