"""Display helpers for MLB / NBA / NHL player profile tables."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.sports.display_stats import display_stats_for_sport, game_log_stat_columns
from src.stats_columns import format_stats_dataframe_for_display

PROFILE_HIDDEN_COLUMNS = frozenset(
    {"player_id", "player_name", "fantasy_points_espn"}
)

# Game log tables: internal keys and redundant date/index (season is in the section title).
PROFILE_GAMELOG_HIDDEN_COLUMNS = frozenset(
    {"game_id", "game_date", "game_index", "season", "log_type"}
)

PROFILE_META_COLUMNS = [
    "season",
    "team",
    "position",
    "games",
    "fantasy_points",
    "fp_per_game",
]


def format_profile_table(
    df: pd.DataFrame,
    *,
    columns: list[str] | None = None,
    hide_columns: frozenset[str] | None = None,
) -> pd.DataFrame:
    """Title-case column labels; hide internal ids."""
    return format_stats_dataframe_for_display(
        df,
        hide_columns=hide_columns or PROFILE_HIDDEN_COLUMNS,
        columns=columns,
    )


def format_game_log_table(
    df: pd.DataFrame,
    sport_id: str,
    position: str | None,
    *,
    log_type: str | None = None,
) -> pd.DataFrame:
    """Profile game log with role-appropriate stat columns."""
    hidden = PROFILE_HIDDEN_COLUMNS | PROFILE_GAMELOG_HIDDEN_COLUMNS
    base = ["team", "opponent", "fantasy_points"]
    stat_cols = game_log_stat_columns(sport_id, position, log_type=log_type)
    cols = [c for c in base if c in df.columns]
    cols += [c for c in stat_cols if c in df.columns and c not in cols]
    return format_profile_table(df, columns=cols, hide_columns=hidden)


def profile_export_columns(sport_id: str, career: pd.DataFrame) -> list[str]:
    """Meta + position-appropriate stat columns present in ``career``."""
    cols = [c for c in PROFILE_META_COLUMNS if c in career.columns]
    seen = set(cols)
    if "position" not in career.columns:
        return cols
    for pos in career["position"].dropna().unique():
        for stat in display_stats_for_sport(sport_id, str(pos)):
            if stat in career.columns and stat not in seen:
                cols.append(stat)
                seen.add(stat)
    return cols


def career_season_totals(career: pd.DataFrame) -> pd.DataFrame:
    """Sum fantasy points (and games) per season for charts and peak season."""
    if career.empty or "season" not in career.columns:
        return career
    agg: dict[str, tuple[str, str]] = {
        "fantasy_points": ("fantasy_points", "sum"),
        "games": ("games", "sum"),
    }
    if "career_z" in career.columns:
        agg["career_z"] = ("career_z", "max")
    from src.analytics.metrics import add_fp_per_game

    out = career.groupby("season", as_index=False).agg(**agg)
    out = out.sort_values("season", ascending=True)
    return add_fp_per_game(out)


def render_grouped_career_stats(
    sport_id: str,
    career: pd.DataFrame,
    *,
    container,
) -> None:
    """
    Tables with stats matched to role (MLB hitting vs pitching, NHL skater vs goalie).
    """
    sid = str(sport_id).strip().lower()
    groups: list[tuple[str | None, pd.DataFrame]] = []

    if sid == "mlb":
        from src.sports.mlb.positions import is_pitcher_position

        pit = career["position"].map(is_pitcher_position)
        groups = [
            ("Hitting", career[~pit]),
            ("Pitching", career[pit]),
        ]
    elif sid == "nhl":
        from src.sports.nhl.positions import is_goalie_position

        g = career["position"].map(is_goalie_position)
        groups = [
            ("Skating", career[~g]),
            ("Goaltending", career[g]),
        ]
    else:
        groups = [(None, career)]

    from src.sports.player_career import sort_career_rows

    for label, subset in groups:
        if subset.empty:
            continue
        subset = sort_career_rows(subset)
        if label:
            container.markdown(f"**{label}**")
        pos = subset.iloc[0]["position"]
        stat_cols = display_stats_for_sport(sid, str(pos) if pos is not None else None)
        extra_set = frozenset(PROFILE_META_COLUMNS)
        cols = [c for c in PROFILE_META_COLUMNS if c in subset.columns]
        cols += [c for c in stat_cols if c in subset.columns and c not in extra_set]
        container.dataframe(
            format_profile_table(subset, columns=cols),
            use_container_width=True,
            hide_index=True,
        )


def season_detail_heading(row: pd.Series, *, multi: bool) -> str | None:
    """Subheading for a season stint (position · team)."""
    if not multi:
        return None
    pos = str(row.get("position") or "").strip()
    team = str(row.get("team") or "").strip()
    if pos and team:
        return f"{pos} · {team}"
    return pos or team or None
