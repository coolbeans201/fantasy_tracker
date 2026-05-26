"""Stat column definitions: ingest, storage, and position-aware display."""

from __future__ import annotations

import pandas as pd

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
    "opponent_team": "opponent",
    "opponent": "opponent",
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
    "opponent": "Opponent",
    "teams": "Teams",
    "season": "Season",
    "week": "Week",
    "games": "Games",
    "seasons_in_window": "Seasons",
    "fantasy_points": "Fantasy Points",
    "fp_per_game": "FP Per Game",
    "weekly_std": "Weekly Std Dev",
    "boom_rate": "Boom Rate",
    "bust_rate": "Bust Rate",
    "worst_week_fp": "Worst Week FP",
    "peer_z_season": "Peer Z (Season)",
    "peer_z_era": "Peer Z (Era)",
    "career_z": "Career Z",
    "draft_ecr": "Draft ECR",
    "finish_rank": "Finish Rank",
    "rank_delta": "Rank Δ",
    "weekly_ecr": "Weekly ECR",
    "best_week": "Best Week",
    "best_week_fp": "Best Week FP",
    "stat": "Stat",
    "diff": "Difference",
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
    "pat_made": "PAT Made",
    "pat_missed": "PAT Missed",
    "fg_missed": "FG Missed",
    "fg_made_0_19": "FG 0-19",
    "fg_made_20_29": "FG 20-29",
    "fg_made_30_39": "FG 30-39",
    "fg_made_40_49": "FG 40-49",
    "fg_made_50_59": "FG 50-59",
    "fg_made_60_": "FG 60+",
    "sacks": "Sacks",
    "def_interceptions": "Def INT",
    "fumble_recoveries": "Fumble Recoveries",
    "safeties": "Safeties",
    "blocked_kicks": "Blocked Kicks",
    "def_touchdowns": "Def TD",
    "return_touchdowns": "Return TD",
    "points_allowed": "Points Allowed",
    "yards_allowed": "Yards Allowed",
    "fantasy_points_kicker": "Fantasy Points (K)",
    "fantasy_points_dst": "Fantasy Points (DST)",
    # MLB
    "runs": "Runs",
    "home_runs": "Home Runs",
    "rbi": "RBI",
    "stolen_bases": "Stolen Bases",
    "walks": "Walks",
    "strikeouts_bat": "Strikeouts (Batting)",
    "batting_avg": "Batting Avg",
    "whip": "WHIP",
    "wins": "Wins",
    "strikeouts_pitch": "Strikeouts (Pitching)",
    "saves": "Saves",
    "innings_pitched": "Innings Pitched",
    "era": "ERA",
    # NBA
    "points": "Points",
    "rebounds": "Rebounds",
    "assists": "Assists",
    "steals": "Steals",
    "blocks": "Blocks",
    "turnovers": "Turnovers",
    "three_pointers": "Three-Pointers",
    # NHL
    "goals": "Goals",
    "plus_minus": "Plus/Minus",
    "shots": "Shots",
    "hits": "Hits",
    "goals_against": "Goals Against",
    "shutouts": "Shutouts",
    "fantasy_points_espn": "Fantasy Points (ESPN)",
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
    "K": [
        "fg_made_0_19",
        "fg_made_20_29",
        "fg_made_30_39",
        "fg_made_40_49",
        "fg_made_50_59",
        "fg_made_60_",
        "fg_missed",
        "pat_made",
        "pat_missed",
    ],
    "DST": [
        "sacks",
        "def_interceptions",
        "fumble_recoveries",
        "safeties",
        "blocked_kicks",
        "def_touchdowns",
        "return_touchdowns",
        "points_allowed",
        "yards_allowed",
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
    """Comma-separated offensive stat columns for SELECT clauses."""
    return ", ".join(STAT_COLUMNS)


def sql_player_stat_select() -> str:
    """Offensive + kicker stat columns for player season/weekly queries."""
    from src.kicker_columns import KICKER_STAT_COLUMNS

    return ", ".join(STAT_COLUMNS + KICKER_STAT_COLUMNS)


def column_display_label(col: str) -> str:
    """Human-readable label for any stored or derived column key."""
    if col in DISPLAY_COLUMN_LABELS:
        return DISPLAY_COLUMN_LABELS[col]
    if col in STAT_LABELS:
        return STAT_LABELS[col]
    from src.ui_text import title_case_ui

    return title_case_ui(col.replace("_", " "))


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
    Stat columns for UI tables.
    Kicker stats only when K alone is selected; DST stats only for DST alone;
    otherwise offensive stats only (no kicker/DST columns).
    """
    from src.kicker_columns import KICKER_STAT_COLUMNS
    from src.positions import (
        DST_POSITION,
        is_dst_only_selection,
        is_kicker_only_selection,
        normalize_fantasy_position,
        normalize_leader_selection,
    )
    from src.team_dst_columns import DST_STAT_COLUMNS

    selected = normalize_leader_selection(positions)

    if is_dst_only_selection(selected):
        return list(DST_STAT_COLUMNS)

    if is_kicker_only_selection(selected):
        return list(KICKER_STAT_COLUMNS)

    seen: list[str] = []
    for pos in selected:
        key = normalize_fantasy_position(pos) or str(pos).strip().upper()
        if key in (DST_POSITION, "K"):
            continue
        for col in POSITION_EMPHASIS.get(key, STAT_COLUMNS):
            if col not in seen:
                seen.append(col)
    for col in STAT_COLUMNS:
        if col not in seen:
            seen.append(col)
    return _collapse_display_stat_columns(seen)


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


def rename_compare_career_merge(
    df: "pd.DataFrame",
    name_a: str,
    name_b: str,
    *,
    include_teams: bool = True,
) -> "pd.DataFrame":
    """Readable title-case columns for Compare all-time season merge table."""
    labels = {
        "season": "Season",
        "fantasy_points_a": f"Fantasy Points ({name_a})",
        "fantasy_points_b": f"Fantasy Points ({name_b})",
        "diff": "Difference",
    }
    if include_teams:
        labels["teams_a"] = f"Teams ({name_a})"
        labels["teams_b"] = f"Teams ({name_b})"
    out = df.rename(columns={k: v for k, v in labels.items() if k in df.columns})
    return round_table_for_display(out)


def _counting_stat_keys() -> frozenset[str]:
    from src.kicker_columns import KICKER_STAT_COLUMNS
    from src.team_dst_columns import DST_STAT_COLUMNS

    return frozenset(STAT_COLUMNS) | frozenset(KICKER_STAT_COLUMNS) | frozenset(DST_STAT_COLUMNS)


_META_INTEGER_KEYS = frozenset({"season", "week", "games", "best_week"})
_META_INTEGER_LABELS = frozenset({"Season", "Week", "Games", "Best Week"})

_DECIMAL_KEYS = frozenset(
    {
        "fantasy_points",
        "fantasy_points_standard",
        "fantasy_points_half_ppr",
        "fantasy_points_full_ppr",
        "fantasy_points_kicker",
        "fantasy_points_dst",
        "fp_per_game",
        "peer_z_season",
        "peer_z_era",
        "career_z",
        "best_week_fp",
        "weekly_std",
        "boom_rate",
        "bust_rate",
        "worst_week_fp",
        "diff",
    }
)

_DECIMAL_DISPLAY_LABELS = frozenset(
    DISPLAY_COLUMN_LABELS[k] for k in _DECIMAL_KEYS if k in DISPLAY_COLUMN_LABELS
)

_COUNTING_DISPLAY_LABELS = frozenset(
    STAT_LABELS[k] for k in _counting_stat_keys() if k in STAT_LABELS
)


def is_decimal_display_column(col: str) -> bool:
    """Fantasy points, Z-scores, rates — show fractional digits."""
    if col in _DECIMAL_KEYS or col in _DECIMAL_DISPLAY_LABELS:
        return True
    if col.startswith("Fantasy Points"):
        return True
    if "Peer Z" in col:
        return True
    return col in {
        "FP Per Game",
        "Difference",
        "Career Z",
        "Weekly Std Dev",
        "Boom Rate",
        "Bust Rate",
        "Worst Week FP",
        "Best Week FP",
    }


def is_counting_display_column(col: str) -> bool:
    """Attempts, yards, TDs, etc. — whole numbers only."""
    if is_decimal_display_column(col):
        return False
    if col in _META_INTEGER_KEYS or col in _META_INTEGER_LABELS:
        return True
    if col in _counting_stat_keys():
        return True
    if col in _COUNTING_DISPLAY_LABELS:
        return True
    return False


def styler_format_for_columns(df: pd.DataFrame) -> dict[str, str]:
    """Pandas Styler format strings keyed by column name."""
    fmt: dict[str, str] = {}
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        if is_decimal_display_column(col):
            fmt[col] = "{:.2f}"
        else:
            fmt[col] = "{:.0f}"
    return fmt


def round_table_for_display(df: pd.DataFrame, decimals: int = 2) -> pd.DataFrame:
    """
    Format numeric columns for UI tables.

    Counting stats (attempts, yards, TDs) and meta fields (season, games) are
    integers. Fantasy points and Z-scores use ``decimals`` decimal places.
    """
    out = df.copy()
    for col in out.columns:
        if not pd.api.types.is_numeric_dtype(out[col]):
            continue
        numeric = pd.to_numeric(out[col], errors="coerce")
        if is_decimal_display_column(col):
            out[col] = numeric.round(decimals)
        elif is_counting_display_column(col):
            out[col] = numeric.round(0).astype("Int64")
        else:
            if numeric.dropna().empty or numeric.dropna().apply(
                lambda x: float(x).is_integer()
            ).all():
                out[col] = numeric.round(0).astype("Int64")
            else:
                out[col] = numeric.round(decimals)
    return out


# Internal keys hidden from default profile / compare raw tables
DEFAULT_HIDDEN_DISPLAY_COLUMNS = frozenset({"player_id"})


def format_stats_dataframe_for_display(
    df: pd.DataFrame,
    *,
    hide_columns: frozenset[str] | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Rename columns for UI display (title-case labels, sport stat names)."""
    hidden = hide_columns if hide_columns is not None else DEFAULT_HIDDEN_DISPLAY_COLUMNS
    if columns is None:
        columns = [c for c in df.columns if c not in hidden]
    else:
        columns = [c for c in columns if c not in hidden]
    return rename_stats_for_display(df, columns=columns)


def rename_stats_for_display(df, columns: list[str] | None = None):
    """Return copy with human-readable column names for UI tables."""
    out = collapse_fumble_columns_df(df)
    if columns is None:
        cols = list(out.columns)
    else:
        cols = [c for c in columns if c in out.columns]
    if cols:
        out = out.loc[:, cols].copy()
    rename_map = {c: column_display_label(c) for c in cols}
    out = out.rename(columns=rename_map)
    if "stat" in out.columns:
        out["stat"] = out["stat"].apply(
            lambda s: column_display_label(s)
            if s in DISPLAY_COLUMN_LABELS or s in STAT_LABELS
            else s
        )
    return round_table_for_display(out)
