"""Stat column definitions: ingest, storage, and position-aware display."""

from __future__ import annotations

# All countable stats stored in DuckDB (summed weekly -> season)
STAT_COLUMNS = [
    "passing_completions",
    "passing_attempts",
    "passing_yards",
    "passing_tds",
    "interceptions",
    "sacks_suffered",
    "carries",
    "rushing_yards",
    "rushing_tds",
    "rushing_fumbles_lost",
    "receptions",
    "targets",
    "receiving_yards",
    "receiving_tds",
    "receiving_fumbles_lost",
    "fumbles_lost",
]

# nflverse / alternate source names -> our schema
NFLVERSE_COL_MAP: dict[str, str] = {
    "player_id": "player_id",
    "gsis_id": "player_id",
    "nfl_id": "player_id",
    "season": "season",
    "week": "week",
    "season_type": "season_type",
    "recent_team": "team",
    "team": "team",
    "position": "position",
    "games": "games",
    "completions": "passing_completions",
    "passing_completions": "passing_completions",
    "attempts": "passing_attempts",
    "passing_attempts": "passing_attempts",
    "passing_yards": "passing_yards",
    "passing_tds": "passing_tds",
    "passing_interceptions": "interceptions",
    "interceptions": "interceptions",
    "sacks_suffered": "sacks_suffered",
    "sacks": "sacks_suffered",
    "carries": "carries",
    "rushing_attempts": "carries",
    "rushing_yards": "rushing_yards",
    "rushing_tds": "rushing_tds",
    "rushing_fumbles_lost": "rushing_fumbles_lost",
    "receptions": "receptions",
    "targets": "targets",
    "receiving_yards": "receiving_yards",
    "receiving_tds": "receiving_tds",
    "receiving_fumbles_lost": "receiving_fumbles_lost",
    "fumbles_lost": "fumbles_lost",
}

# UI labels for non-stat table columns (stats use STAT_LABELS)
DISPLAY_COLUMN_LABELS: dict[str, str] = {
    "player_name": "Player",
    "position": "Position",
    "team": "Team",
    "teams": "Teams",
    "season": "Season",
    "week": "Week",
    "games": "Games",
    "fantasy_points": "Fantasy Points",
    "peer_z_season": "Peer Z (Season)",
    "peer_z_era": "Peer Z (Era)",
    "career_z": "Career Z",
    "best_week": "Best Week",
    "best_week_fp": "Best Week FP",
}

STAT_LABELS: dict[str, str] = {
    "passing_completions": "Passing Completions",
    "passing_attempts": "Passing Attempts",
    "passing_yards": "Passing Yards",
    "passing_tds": "Passing TDs",
    "interceptions": "Interceptions",
    "sacks_suffered": "Sacks",
    "carries": "Carries",
    "rushing_yards": "Rushing Yards",
    "rushing_tds": "Rushing TDs",
    "rushing_fumbles_lost": "Rushing Fumbles Lost",
    "receptions": "Receptions",
    "targets": "Targets",
    "receiving_yards": "Receiving Yards",
    "receiving_tds": "Receiving TDs",
    "receiving_fumbles_lost": "Receiving Fumbles Lost",
    "fumbles_lost": "Fumbles Lost",
}

# Stored separately in DB; shown as one "Fumbles Lost" column in the UI
FUMBLE_STAT_COLUMNS = ("rushing_fumbles_lost", "receiving_fumbles_lost", "fumbles_lost")
_HIDDEN_DISPLAY_STAT_COLUMNS = frozenset({"rushing_fumbles_lost", "receiving_fumbles_lost"})

# Stats emphasized in tables when viewing a position (all stats still stored & available)
POSITION_EMPHASIS: dict[str, list[str]] = {
    "QB": [
        "passing_attempts",
        "passing_completions",
        "passing_yards",
        "passing_tds",
        "interceptions",
        "sacks_suffered",
        "carries",
        "rushing_yards",
        "rushing_tds",
        "fumbles_lost",
    ],
    "RB": [
        "carries",
        "rushing_yards",
        "rushing_tds",
        "targets",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        "fumbles_lost",
        "passing_yards",
        "passing_tds",
    ],
    "WR": [
        "targets",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        "carries",
        "rushing_yards",
        "rushing_tds",
        "fumbles_lost",
    ],
    "TE": [
        "targets",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        "carries",
        "rushing_yards",
        "rushing_tds",
        "fumbles_lost",
    ],
}

FANTASY_POINT_COLUMNS = [
    "fantasy_points_standard",
    "fantasy_points_half_ppr",
    "fantasy_points_full_ppr",
]


def resolve_player_name(source: "pd.DataFrame") -> "pd.Series":
    """
    Prefer nflverse player_display_name (e.g. Ameer Abdullah) over player_name (A.Abdullah).
    """
    import pandas as pd

    display = (
        source["player_display_name"].astype(str).str.strip()
        if "player_display_name" in source.columns
        else None
    )
    short = (
        source["player_name"].astype(str).str.strip()
        if "player_name" in source.columns
        else None
    )
    if display is not None:
        display = display.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "<NA>": pd.NA})
    if short is not None:
        short = short.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "<NA>": pd.NA})

    if display is not None and short is not None:
        return display.fillna(short)
    if display is not None:
        return display
    if short is not None:
        return short
    return pd.Series([pd.NA] * len(source), index=source.index)


def sql_stat_select() -> str:
    """Comma-separated stat columns for SELECT clauses."""
    return ", ".join(STAT_COLUMNS)


def column_display_label(col: str) -> str:
    """Human-readable label for any stored or derived column key."""
    if col in DISPLAY_COLUMN_LABELS:
        return DISPLAY_COLUMN_LABELS[col]
    if col in STAT_LABELS:
        return STAT_LABELS[col]
    return col.replace("_", " ").title()


def stat_display_label(col: str) -> str:
    """Human-readable label for a stored stat column key."""
    return column_display_label(col)


def combined_fumbles_lost(row) -> float:
    """Total fumbles lost for display (avoid double-counting stored components)."""
    total = float(row.get("fumbles_lost", 0) or 0)
    if total > 0:
        return total
    return float(row.get("rushing_fumbles_lost", 0) or 0) + float(
        row.get("receiving_fumbles_lost", 0) or 0
    )


def stat_display_value(row, col: str) -> float:
    """Numeric value for a display stat column (combines fumble sources when needed)."""
    if col == "fumbles_lost":
        return combined_fumbles_lost(row)
    return float(row.get(col, 0) or 0)


def _collapse_display_stat_columns(cols: list[str]) -> list[str]:
    """Merge rush/rec fumble columns into a single Fumbles Lost display column."""
    has_fumble = any(c in FUMBLE_STAT_COLUMNS for c in cols)
    out: list[str] = []
    for col in cols:
        if col in _HIDDEN_DISPLAY_STAT_COLUMNS:
            continue
        if col not in out:
            out.append(col)
    if has_fumble and "fumbles_lost" not in out:
        out.append("fumbles_lost")
    return out


def display_stats_for_positions(positions: list[str] | None) -> list[str]:
    """
    Stat columns to show in UI: union of position-emphasis sets, then remaining stats.
    Always returns every stored stat column (no filtering out cross-position stats).
    """
    if not positions:
        ordered = list(STAT_COLUMNS)
    else:
        from src.positions import normalize_fantasy_position

        seen: list[str] = []
        for pos in positions:
            key = normalize_fantasy_position(pos) or pos
            for col in POSITION_EMPHASIS.get(key, STAT_COLUMNS):
                if col not in seen:
                    seen.append(col)
        for col in STAT_COLUMNS:
            if col not in seen:
                seen.append(col)
        ordered = seen
    return _collapse_display_stat_columns(ordered)


def build_stat_compare_frame(
    row_a,
    row_b,
    name_a: str,
    name_b: str,
    positions: list[str] | None,
) -> "pd.DataFrame":
    """Side-by-side stat comparison with readable labels and combined fumbles."""
    import pandas as pd

    rows = []
    for col in display_stats_for_positions(positions):
        rows.append(
            {
                "stat": stat_display_label(col),
                name_a: stat_display_value(row_a, col),
                name_b: stat_display_value(row_b, col),
                "diff": stat_display_value(row_a, col) - stat_display_value(row_b, col),
            }
        )
    return pd.DataFrame(rows)


def collapse_fumble_columns_df(df):
    """One Fumbles Lost column with combined values; drop rush/rec fumble columns."""
    import pandas as pd

    if not any(c in df.columns for c in FUMBLE_STAT_COLUMNS):
        return df
    out = df.copy()
    out["fumbles_lost"] = out.apply(combined_fumbles_lost, axis=1)
    drop_cols = [c for c in _HIDDEN_DISPLAY_STAT_COLUMNS if c in out.columns]
    return out.drop(columns=drop_cols, errors="ignore")


def rename_stats_for_display(df, columns: list[str] | None = None):
    """Return copy with human-readable column names for UI tables."""
    out = collapse_fumble_columns_df(df)
    cols = columns or list(out.columns)
    rename_map = {
        c: column_display_label(c) for c in cols if c in out.columns
    }
    out = out.rename(columns=rename_map)
    if "stat" in out.columns:
        out["stat"] = out["stat"].apply(
            lambda s: column_display_label(s)
            if s in DISPLAY_COLUMN_LABELS or s in STAT_LABELS
            else s
        )
    return out
