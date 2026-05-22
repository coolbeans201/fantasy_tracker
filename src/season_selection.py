"""Sidebar season window: single year, contiguous range, or hand-picked seasons."""

from __future__ import annotations

SEASON_MODE_SINGLE = "single"
SEASON_MODE_RANGE = "range"
SEASON_MODE_PICK = "pick"

SEASON_MODES = (SEASON_MODE_SINGLE, SEASON_MODE_RANGE, SEASON_MODE_PICK)


def resolve_season_window(
    ingested: list[int],
    mode: str,
    *,
    single_year: int | None = None,
    range_start: int | None = None,
    range_end: int | None = None,
    picked: list[int] | None = None,
) -> list[int]:
    """
    Return selected seasons (newest first), intersected with ingested years.
    Empty list if nothing valid is selected.
    """
    available = sorted({int(y) for y in ingested})
    if not available:
        return []

    if mode == SEASON_MODE_SINGLE:
        if single_year is None:
            return [available[-1]]
        year = int(single_year)
        return [year] if year in available else []

    if mode == SEASON_MODE_RANGE:
        if range_start is None or range_end is None:
            return list(reversed(available))
        lo = min(int(range_start), int(range_end))
        hi = max(int(range_start), int(range_end))
        return sorted((y for y in available if lo <= y <= hi), reverse=True)

    if mode == SEASON_MODE_PICK:
        if not picked:
            return []
        chosen = {int(y) for y in picked}
        return sorted((y for y in available if y in chosen), reverse=True)

    return [available[-1]]


def format_season_label(seasons: list[int]) -> str:
    """Human-readable window for titles and CSV filenames."""
    if not seasons:
        return ""
    ordered = sorted({int(s) for s in seasons})
    if len(ordered) == 1:
        return str(ordered[0])
    if ordered == list(range(ordered[0], ordered[-1] + 1)):
        return f"{ordered[0]}-{ordered[-1]}"
    return "_".join(str(y) for y in ordered)


def format_season_span(seasons: list[int]) -> str:
    """Display span with en-dash (e.g. 2018–2022 or 2019, 2021, 2024)."""
    if not seasons:
        return ""
    ordered = sorted({int(s) for s in seasons})
    if len(ordered) == 1:
        return str(ordered[0])
    if ordered == list(range(ordered[0], ordered[-1] + 1)):
        return f"{ordered[0]}–{ordered[-1]}"
    return ", ".join(str(y) for y in ordered)


def is_multi_season_window(seasons: list[int]) -> bool:
    return len(seasons) > 1


def sidebar_window_caption(seasons: list[int], *, mode: str) -> str:
    """Short sidebar note for the active season window."""
    if not seasons:
        return "No seasons selected in this window."
    span = format_season_span(seasons)
    if mode == SEASON_MODE_SINGLE:
        return f"Viewing **{span}**."
    if len(seasons) == 1:
        return f"Window: **{span}** (one season)."
    return f"Window: **{span}** ({len(seasons)} seasons)."


def metric_window_caption(seasons: list[int]) -> str | None:
    """Theme C3: Z-scores and weekly shape stay season-scoped."""
    if not is_multi_season_window(seasons):
        return None
    return (
        "Multi-season window: totals and FP/G sum across selected years. "
        "**Peer Z**, **career Z**, and **weekly** metrics use one season at a time."
    )
