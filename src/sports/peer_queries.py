"""Season stat frames for peer Z analysis (MLB / NBA / NHL)."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.sports.peer_positions import positions_for_peer_grouping
from src.sports.player_seasons import stats_table


def _fetch(conn: duckdb.DuckDBPyConnection, sql: str, params: list) -> pd.DataFrame:
    df = conn.execute(sql, params).df()
    if len(df.columns):
        df.columns = [str(c).lower() for c in df.columns]
    return df


def season_stats_for_peer_analysis(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    *,
    season: int | None = None,
    min_games: int | None = None,
) -> pd.DataFrame:
    """
    Player-season rows with fantasy_points and normalized position for peer Z.

    When season is None, returns all ingested seasons for the sport (era Z).
    """
    table = stats_table(sport_id)
    sid = str(sport_id).strip().lower()
    extra_cols = ""
    if sid == "mlb":
        extra_cols = ", innings_pitched"
    query = f"""
        SELECT
            player_id,
            season,
            position,
            games,
            fantasy_points_espn AS fantasy_points
            {extra_cols}
        FROM {table}
        WHERE 1=1
    """
    params: list = []
    if season is not None:
        query += " AND season = ?"
        params.append(int(season))
    if min_games and min_games > 0:
        query += " AND games >= ?"
        params.append(int(min_games))
    df = _fetch(conn, query, params)
    if df.empty:
        return df
    if sid in ("mlb", "nhl"):
        # One season total per player for peer cohort (not per team stint).
        group_cols = ["player_id", "season", "position"]
        agg: dict[str, tuple[str, str]] = {
            "games": ("games", "sum"),
            "fantasy_points": ("fantasy_points", "sum"),
        }
        if sid == "mlb" and "innings_pitched" in df.columns:
            agg["innings_pitched"] = ("innings_pitched", "sum")
        df = df.groupby(group_cols, as_index=False).agg(**agg)
    df["position"] = df["position"].apply(
        lambda p: positions_for_peer_grouping(sport_id, p)
    )
    return df.dropna(subset=["position"])
