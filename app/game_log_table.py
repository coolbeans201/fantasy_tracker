"""Strong/weak game highlighting for sport profile game logs."""

from __future__ import annotations

import pandas as pd

from src.analytics.game_consistency import game_boom_bust_tags
from src.stats_columns import styler_format_for_columns
from src.ui_text import title_case_ui

STRONG_GAME_STYLE = "background-color: #c8e6c9; font-weight: 600"
WEAK_GAME_STYLE = "background-color: #ffcdd2; font-weight: 600"


def add_game_highlight_column(
    display_df: pd.DataFrame,
    games_df: pd.DataFrame,
    *,
    p25: float | None,
    p75: float | None,
) -> pd.DataFrame:
    tags = game_boom_bust_tags(games_df, p25=p25, p75=p75)
    if not any(tags):
        return display_df

    out = display_df.copy()
    label = title_case_ui("Game Type")
    insert_at = len(out.columns)
    if "Fantasy Points" in out.columns:
        insert_at = list(out.columns).index("Fantasy Points")
    out.insert(insert_at, label, tags.values)
    return out


def style_game_log_table(
    display_df: pd.DataFrame,
    games_df: pd.DataFrame,
    *,
    p25: float | None,
    p75: float | None,
):
    tags = game_boom_bust_tags(games_df, p25=p25, p75=p75)

    def _row_style(row: pd.Series) -> list[str]:
        n = len(row)
        try:
            tag = tags.loc[row.name]
        except KeyError:
            return [""] * n
        if tag == "Strong":
            return [STRONG_GAME_STYLE] * n
        if tag == "Weak":
            return [WEAK_GAME_STYLE] * n
        return [""] * n

    styler = display_df.style.apply(_row_style, axis=1)
    fmt = styler_format_for_columns(display_df)
    if fmt:
        styler = styler.format(fmt, na_rep="—")
    return styler
