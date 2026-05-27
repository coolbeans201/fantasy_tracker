"""Career season rows for sport players."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.analytics.metrics import add_fp_per_game
from src.analytics.sport_variance import compute_career_z_sport
from src.sports.player_seasons import stats_table
from src.text_encoding import normalize_unicode_series


def sort_career_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Chronological order (oldest season first), matching NFL player profile."""
    if df.empty or "season" not in df.columns:
        return df
    sort_cols = ["season"]
    ascending = [True]
    for col in ("team", "position"):
        if col in df.columns:
            sort_cols.append(col)
            ascending.append(True)
    return df.sort_values(sort_cols, ascending=ascending, na_position="last").reset_index(
        drop=True
    )


def player_career_seasons(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    player_id: str,
) -> pd.DataFrame:
    """All season rows for a player (oldest first), with fantasy_points alias."""
    table = stats_table(sport_id)
    df = conn.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE player_id = ?
        ORDER BY season ASC, team ASC NULLS LAST, position ASC NULLS LAST
        """,
        [str(player_id).strip()],
    ).df()
    if df.empty:
        return df
    df.columns = [str(c).lower() for c in df.columns]
    if "player_name" in df.columns:
        df["player_name"] = normalize_unicode_series(df["player_name"])
    if "fantasy_points_espn" in df.columns:
        df["fantasy_points"] = df["fantasy_points_espn"]
    df = add_fp_per_game(df)
    df = compute_career_z_sport(df, sport_id)
    return sort_career_rows(df)


def compare_player_seasons(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    player_id_a: str,
    player_id_b: str,
    *,
    season: int | None = None,
    seasons: list[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df_a = player_career_seasons(conn, sport_id, player_id_a)
    df_b = player_career_seasons(conn, sport_id, player_id_b)
    if season is not None:
        yr = int(season)
        df_a = df_a[df_a["season"].astype(int) == yr]
        df_b = df_b[df_b["season"].astype(int) == yr]
    elif seasons:
        window = {int(s) for s in seasons}
        df_a = df_a[df_a["season"].astype(int).isin(window)]
        df_b = df_b[df_b["season"].astype(int).isin(window)]
    return df_a, df_b
