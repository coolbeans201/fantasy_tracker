"""Boom/bust week highlighting for weekly tables."""

from __future__ import annotations

import pandas as pd

from src.analytics.consistency import week_boom_bust_tags
from src.stats_columns import styler_format_for_columns

BOOM_WEEK_STYLE = "background-color: #c8e6c9; font-weight: 600"
BUST_WEEK_STYLE = "background-color: #ffcdd2; font-weight: 600"


def add_weekly_highlight_column(
    display_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    *,
    p25: float | None,
    p75: float | None,
) -> pd.DataFrame:
    tags = week_boom_bust_tags(weekly_df, p25=p25, p75=p75)
    if not any(tags):
        return display_df

    out = display_df.copy()
    week_col = "Week" if "Week" in out.columns else "week"
    insert_at = list(out.columns).index(week_col) + 1 if week_col in out.columns else 0
    out.insert(insert_at, "Week Type", tags.values)
    return out


def style_weekly_breakdown(
    display_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    *,
    p25: float | None,
    p75: float | None,
):
    tags = week_boom_bust_tags(weekly_df, p25=p25, p75=p75)

    def _row_style(row: pd.Series) -> list[str]:
        n = len(row)
        try:
            tag = tags.loc[row.name]
        except KeyError:
            return [""] * n
        if tag == "Boom":
            return [BOOM_WEEK_STYLE] * n
        if tag == "Bust":
            return [BUST_WEEK_STYLE] * n
        return [""] * n

    styler = display_df.style.apply(_row_style, axis=1)
    fmt = styler_format_for_columns(display_df)
    if fmt:
        styler = styler.format(fmt, na_rep="—")
    return styler
