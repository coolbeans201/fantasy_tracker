"""SQL query helpers for the Streamlit app."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.positions import expand_position_filter
from src.scoring.calc import fp_column_for_preset, resolve_preset
from src.settings import get_min_games_default
from src.stats_columns import sql_stat_select


def get_fp_column(preset: str) -> str:
    return fp_column_for_preset(resolve_preset(preset))


def _fetch_df(
    conn: duckdb.DuckDBPyConnection,
    sql: str,
    params: list | None = None,
) -> pd.DataFrame:
    """Run SQL and normalize column names (lowercase) for consistent pandas access."""
    if params is not None:
        df = conn.execute(sql, params).df()
    else:
        df = conn.execute(sql).df()
    if len(df.columns) > 0:
        df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def season_leaders(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    preset: str,
    positions: list[str] | None = None,
    team: str | None = None,
    min_games: int | None = None,
    use_team_splits: bool = False,
) -> pd.DataFrame:
    if min_games is None:
        min_games = get_min_games_default()

    fp_col = get_fp_column(preset)
    table = "season_team_stats" if (use_team_splits or team) else "season_stats"
    team_col = "team" if table == "season_team_stats" else "teams"
    stats = sql_stat_select()

    query = f"""
        SELECT
            player_id,
            player_name,
            season,
            position,
            {team_col} AS team,
            games,
            {fp_col} AS fantasy_points,
            {stats}
        FROM {table}
        WHERE season = ?
          AND games >= ?
          AND position IS NOT NULL
    """
    params: list = [season, min_games]

    expanded = expand_position_filter(positions)
    if expanded:
        placeholders = ",".join(["?"] * len(expanded))
        query += f" AND position IN ({placeholders})"
        params.extend(expanded)

    if team and table == "season_team_stats":
        query += " AND team = ?"
        params.append(team)
    elif team and table == "season_stats":
        query += " AND teams LIKE ?"
        params.append(f"%{team}%")

    query += f" ORDER BY {fp_col} DESC NULLS LAST"
    return _fetch_df(conn, query, params)


def player_seasons(
    conn: duckdb.DuckDBPyConnection,
    player_id: str,
    preset: str,
) -> pd.DataFrame:
    fp_col = get_fp_column(preset)
    stats = sql_stat_select()
    return _fetch_df(
        conn,
        f"""
        SELECT
            player_name, season, position, teams, games,
            {fp_col} AS fantasy_points,
            best_week, best_week_fp,
            {stats}
        FROM season_stats
        WHERE player_id = ?
        ORDER BY season
        """,
        [player_id],
    )


def player_team_splits(
    conn: duckdb.DuckDBPyConnection,
    player_id: str,
    season: int,
    preset: str,
) -> pd.DataFrame:
    fp_col = get_fp_column(preset)
    stats = sql_stat_select()
    return _fetch_df(
        conn,
        f"""
        SELECT season, team, games, position, {fp_col} AS fantasy_points, {stats}
        FROM season_team_stats
        WHERE player_id = ? AND season = ?
        ORDER BY fantasy_points DESC
        """,
        [player_id, season],
    )


def player_weekly(
    conn: duckdb.DuckDBPyConnection,
    player_id: str,
    season: int,
    preset: str,
) -> pd.DataFrame:
    fp_col = get_fp_column(preset)
    stats = sql_stat_select()
    return _fetch_df(
        conn,
        f"""
        SELECT week, team, position, games, {fp_col} AS fantasy_points, {stats}
        FROM weekly_stats
        WHERE player_id = ? AND season = ? AND season_type = 'REG'
        ORDER BY week
        """,
        [player_id, season],
    )


def season_stats_for_peer_analysis(
    conn: duckdb.DuckDBPyConnection,
    season: int | None,
    preset: str,
    min_games: int | None = None,
) -> pd.DataFrame:
    """All season rows with full stats for Z-score cohorts."""
    if min_games is None:
        min_games = get_min_games_default()
    fp_col = get_fp_column(preset)
    stats = sql_stat_select()
    cols = ["player_id", "season", "position", "games", "fantasy_points"]
    if season is not None:
        df = _fetch_df(
            conn,
            f"""
            SELECT player_id, season, position, games, {fp_col} AS fantasy_points, {stats}
            FROM season_stats WHERE season = ? AND games >= ?
            """,
            [season, min_games],
        )
    else:
        df = _fetch_df(
            conn,
            f"""
            SELECT player_id, season, position, games, {fp_col} AS fantasy_points, {stats}
            FROM season_stats WHERE games >= ?
            """,
            [min_games],
        )
    if df.empty and len(df.columns) == 0:
        return pd.DataFrame(columns=cols)
    return df


def compare_players(
    conn: duckdb.DuckDBPyConnection,
    player_a: str,
    player_b: str,
    preset: str,
    season: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    fp_col = get_fp_column(preset)
    stats = sql_stat_select()
    if season:
        q = f"""
            SELECT player_id, player_name, season, teams, games, position,
                   {fp_col} AS fantasy_points, {stats}
            FROM season_stats
            WHERE player_id IN (?, ?) AND season = ?
        """
        df = _fetch_df(conn, q, [player_a, player_b, season])
    else:
        q = f"""
            SELECT player_id, player_name, season, teams, games, position,
                   {fp_col} AS fantasy_points, {stats}
            FROM season_stats
            WHERE player_id IN (?, ?)
            ORDER BY player_id, season
        """
        df = _fetch_df(conn, q, [player_a, player_b])
    a = df[df["player_id"] == player_a].copy()
    b = df[df["player_id"] == player_b].copy()
    return a, b


def search_players(
    conn: duckdb.DuckDBPyConnection,
    query: str = "",
    limit: int = 500,
) -> pd.DataFrame:
    if query.strip():
        pattern = f"%{query.strip()}%"
        return _fetch_df(
            conn,
            """
            SELECT player_id, player_name, position, last_season
            FROM players
            WHERE player_name ILIKE ?
            ORDER BY last_season DESC NULLS LAST, player_name
            LIMIT ?
            """,
            [pattern, limit],
        )
    return _fetch_df(
        conn,
        """
        SELECT player_id, player_name, position, last_season
        FROM players
        ORDER BY last_season DESC NULLS LAST, player_name
        LIMIT ?
        """,
        [limit],
    )


def teams_for_season(conn: duckdb.DuckDBPyConnection, season: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT team FROM season_team_stats
        WHERE season = ? ORDER BY team
        """,
        [season],
    ).fetchall()
    return [r[0] for r in rows if r[0]]
