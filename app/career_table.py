"""Styled career tables and peak/prime helpers for Player Profile."""

from __future__ import annotations

import pandas as pd

from src.stats_columns import styler_format_for_columns

PEAK_ROW_STYLE = "background-color: #ffcc80; font-weight: 600"
PRIME_ROW_STYLE = "background-color: #c8e6c9"
PEAK_AND_PRIME_ROW_STYLE = (
    "background-color: #ffe0b2; font-weight: 600; "
    "border-left: 5px solid #2e7d32; box-shadow: inset 0 0 0 1px #2e7d32"
)


def prime_season_years(career: pd.DataFrame) -> list[int]:
    """Qualified seasons with career Z above 1."""
    if career.empty or "career_z" not in career.columns:
        return []
    if "peer_qualified" in career.columns:
        mask = career["peer_qualified"] & (career["career_z"] > 1)
    else:
        mask = career["career_z"] > 1
    return career.loc[mask, "season"].astype(int).tolist()


def peak_and_prime_overlap(
    peak_season: int | None,
    prime_seasons: list[int] | None,
) -> list[int]:
    if peak_season is None or not prime_seasons:
        return []
    peak = int(peak_season)
    return [yr for yr in prime_seasons if int(yr) == peak]


def season_highlight_tags(
    season_years: pd.Series,
    *,
    peak_season: int | None,
    prime_seasons: list[int] | None,
) -> pd.Series:
    """Per-row labels: Peak, Prime, Peak · Prime, or empty."""
    prime_set = set(prime_seasons or [])
    peak = int(peak_season) if peak_season is not None else None
    tags: list[str] = []
    for yr in season_years.astype(int):
        is_peak = peak is not None and int(yr) == peak
        is_prime = int(yr) in prime_set
        if is_peak and is_prime:
            tags.append("Peak · Prime")
        elif is_peak:
            tags.append("Peak")
        elif is_prime:
            tags.append("Prime")
        else:
            tags.append("")
    return pd.Series(tags, index=season_years.index)


def format_peak_prime_caption(
    peak_season: int | None,
    prime_seasons: list[int] | None,
) -> str:
    """User-facing summary including combined peak+prime seasons."""
    prime_only = sorted(
        set(prime_seasons or []) - {int(peak_season)} if peak_season is not None else set()
    )
    both = peak_and_prime_overlap(peak_season, prime_seasons)
    parts: list[str] = []

    if both:
        parts.append(
            f"**{both[0]}** is both peak FP and a prime season (orange + green ring on chart, "
            f"**Peak · Prime** in table)"
        )
    elif peak_season is not None:
        parts.append(f"Peak season: **{peak_season}** (orange)")

    if prime_only:
        parts.append(
            f"Other prime seasons (career Z > 1): **{', '.join(str(y) for y in prime_only)}** (green)"
        )
    elif prime_seasons and not both:
        parts.append(
            f"Prime seasons: **{', '.join(str(y) for y in sorted(prime_seasons))}** (green)"
        )

    return " · ".join(parts) if parts else ""


def add_highlight_column(
    display_df: pd.DataFrame,
    season_years: pd.Series,
    *,
    peak_season: int | None,
    prime_seasons: list[int] | None,
) -> pd.DataFrame:
    """Insert Highlight column after Season when any tags exist."""
    tags = season_highlight_tags(
        season_years, peak_season=peak_season, prime_seasons=prime_seasons
    )
    if not any(tags):
        return display_df

    out = display_df.copy()
    season_col = "Season" if "Season" in out.columns else "season"
    if season_col not in out.columns:
        out.insert(0, "Highlight", tags.values)
        return out

    insert_at = list(out.columns).index(season_col) + 1
    out.insert(insert_at, "Highlight", tags.values)
    return out


def style_career_breakdown(
    display_df: pd.DataFrame,
    season_years: pd.Series,
    *,
    peak_season: int | None,
    prime_seasons: list[int] | None,
):
    """Highlight peak, prime, and combined peak+prime rows."""
    prime_set = set(prime_seasons or [])
    peak = int(peak_season) if peak_season is not None else None

    def _row_style(row: pd.Series) -> list[str]:
        n = len(row)
        try:
            yr = int(season_years.loc[row.name])
        except (KeyError, TypeError, ValueError):
            return [""] * n
        if peak is not None and yr == peak and yr in prime_set:
            return [PEAK_AND_PRIME_ROW_STYLE] * n
        if peak is not None and yr == peak:
            return [PEAK_ROW_STYLE] * n
        if yr in prime_set:
            return [PRIME_ROW_STYLE] * n
        return [""] * n

    styler = display_df.style.apply(_row_style, axis=1)
    fmt = styler_format_for_columns(display_df)
    if fmt:
        styler = styler.format(fmt, na_rep="—")
    return styler
