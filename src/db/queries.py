"""SQL query helpers for the Streamlit app."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.entities import dst_team_from_entity, is_dst_entity
from src.teams import dst_entity_display_name, team_search_patterns
from src.positions import (
    DST_POSITION,
    expand_position_filter,
    is_dst_only_selection,
    normalize_leader_selection,
)
from src.scoring.calc import fantasy_points_sql_expr, offensive_fp_column, resolve_preset
from src.scoring.special import DST_FP_COLUMN
from src.settings import get_min_games_default
from src.stats_columns import sql_player_stat_select, sql_stat_select
from src.team_dst_columns import sql_dst_stat_select


def get_fp_column(preset: str) -> str:
    return offensive_fp_column(preset)


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


def _split_leader_positions(positions: list[str] | None) -> tuple[list[str] | None, bool]:
    selected = normalize_leader_selection(positions)
    want_dst = is_dst_only_selection(selected)
    if want_dst:
        return None, True
    return selected, False


def dst_season_leaders(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    team: str | None = None,
    min_games: int | None = None,
) -> pd.DataFrame:
    """DST leaderboard — min_games is ignored (every team plays each week)."""
    del min_games  # noqa: ARG001 — API parity with player leaders

    stats = sql_dst_stat_select()
    query = f"""
        SELECT
            team AS player_name,
            '{DST_POSITION}' AS position,
            team,
            season,
            games,
            {DST_FP_COLUMN} AS fantasy_points,
            {stats}
        FROM team_defense_season
        WHERE season = ?
    """
    params: list = [season]
    if team:
        query += " AND team = ?"
        params.append(team)
    query += f" ORDER BY {DST_FP_COLUMN} DESC NULLS LAST"
    return _fetch_df(conn, query, params)


def _player_season_leaders(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    preset: str,
    positions: list[str] | None,
    team: str | None,
    min_games: int,
    use_team_splits: bool,
) -> pd.DataFrame:
    fp_expr = fantasy_points_sql_expr(preset)
    table = "season_team_stats" if (use_team_splits or team) else "season_stats"
    team_col = "team" if table == "season_team_stats" else "teams"
    stats = sql_player_stat_select()

    query = f"""
        SELECT
            player_id,
            player_name,
            season,
            position,
            {team_col} AS team,
            games,
            {fp_expr} AS fantasy_points,
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

    query += f" ORDER BY fantasy_points DESC NULLS LAST"
    return _fetch_df(conn, query, params)


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

    player_pos, want_dst = _split_leader_positions(positions)
    frames: list[pd.DataFrame] = []

    if want_dst and not use_team_splits:
        frames.append(dst_season_leaders(conn, season, team=team, min_games=min_games))
    elif player_pos:
        frames.append(
            _player_season_leaders(
                conn, season, preset, player_pos, team, min_games, use_team_splits
            )
        )

    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, ignore_index=True)


def _aggregate_leader_window(per_season: pd.DataFrame) -> pd.DataFrame:
    """Sum qualified player-season rows into one row per player (or team for DST)."""
    if per_season.empty:
        return per_season

    if "player_id" in per_season.columns:
        id_col = "player_id"
    elif "team" in per_season.columns:
        id_col = "team"
    else:
        return per_season
    stat_cols = [
        c
        for c in per_season.columns
        if c
        not in {
            id_col,
            "player_name",
            "position",
            "team",
            "teams",
            "season",
            "games",
            "fantasy_points",
        }
        and pd.api.types.is_numeric_dtype(per_season[c])
    ]

    agg: dict = {
        "player_name": ("player_name", "last"),
        "position": ("position", "last"),
        "seasons_in_window": ("season", "nunique"),
        "games": ("games", "sum"),
        "fantasy_points": ("fantasy_points", "sum"),
    }
    if "team" in per_season.columns:
        agg["team"] = ("team", "last")
    if "teams" in per_season.columns:
        agg["teams"] = ("teams", "last")
    for col in stat_cols:
        agg[col] = (col, "sum")

    grouped = per_season.groupby(id_col, as_index=False).agg(**agg)
    if "fantasy_points" in grouped.columns and "games" in grouped.columns:
        grouped["fp_per_game"] = grouped["fantasy_points"] / grouped["games"].replace(0, pd.NA)
    return grouped


def season_leaders_window(
    conn: duckdb.DuckDBPyConnection,
    seasons: list[int],
    preset: str,
    positions: list[str] | None = None,
    min_games: int | None = None,
) -> pd.DataFrame:
    """
    Window leaderboard: sum FP and games across seasons (min games applied per season).
    Team filter and team splits are not supported in window mode.
    """
    if not seasons:
        return pd.DataFrame()
    if min_games is None:
        min_games = get_min_games_default()

    frames: list[pd.DataFrame] = []
    for yr in seasons:
        part = season_leaders(
            conn,
            int(yr),
            preset,
            positions=positions,
            team=None,
            min_games=min_games,
            use_team_splits=False,
        )
        if not part.empty:
            part = part.copy()
            part["season"] = int(yr)
            frames.append(part)

    if not frames:
        return pd.DataFrame()
    per_season = pd.concat(frames, ignore_index=True)
    return _aggregate_leader_window(per_season)


def dst_team_seasons(conn: duckdb.DuckDBPyConnection, team: str) -> pd.DataFrame:
    stats = sql_dst_stat_select()
    return _fetch_df(
        conn,
        f"""
        SELECT
            team AS player_name,
            season,
            '{DST_POSITION}' AS position,
            team AS teams,
            games,
            {DST_FP_COLUMN} AS fantasy_points,
            best_week,
            best_week_fp,
            {stats}
        FROM team_defense_season
        WHERE team = ?
        ORDER BY season
        """,
        [team],
    )


def dst_team_weekly(
    conn: duckdb.DuckDBPyConnection,
    team: str,
    season: int,
) -> pd.DataFrame:
    stats = sql_dst_stat_select()
    return _fetch_df(
        conn,
        f"""
        SELECT
            week,
            team,
            opponent,
            '{DST_POSITION}' AS position,
            games,
            {DST_FP_COLUMN} AS fantasy_points,
            {stats}
        FROM team_defense_weekly
        WHERE team = ? AND season = ? AND season_type = 'REG'
        ORDER BY week
        """,
        [team, season],
    )


def dst_season_stats_for_peer_analysis(
    conn: duckdb.DuckDBPyConnection,
    season: int,
    min_games: int | None = None,
) -> pd.DataFrame:
    """All team defenses that season (no min-games filter)."""
    del min_games  # noqa: ARG001
    return _fetch_df(
        conn,
        f"""
        SELECT team AS player_id, season, '{DST_POSITION}' AS position, games,
               {DST_FP_COLUMN} AS fantasy_points
        FROM team_defense_season
        WHERE season = ?
        """,
        [season],
    )


def entity_seasons(
    conn: duckdb.DuckDBPyConnection,
    entity_id: str,
    preset: str,
) -> pd.DataFrame:
    if is_dst_entity(entity_id):
        return dst_team_seasons(conn, dst_team_from_entity(entity_id))
    return player_seasons(conn, entity_id, preset)


def entity_weekly(
    conn: duckdb.DuckDBPyConnection,
    entity_id: str,
    season: int,
    preset: str,
) -> pd.DataFrame:
    if is_dst_entity(entity_id):
        return dst_team_weekly(conn, dst_team_from_entity(entity_id), season)
    return player_weekly(conn, entity_id, season, preset)


def entity_all_weekly(
    conn: duckdb.DuckDBPyConnection,
    entity_id: str,
    preset: str,
) -> pd.DataFrame:
    """All regular-season weeks for an entity (for preset-specific best week)."""
    if is_dst_entity(entity_id):
        team = dst_team_from_entity(entity_id)
        stats = sql_dst_stat_select()
        return _fetch_df(
            conn,
            f"""
            SELECT season, week, team, opponent, '{DST_POSITION}' AS position, games,
                   {DST_FP_COLUMN} AS fantasy_points, {stats}
            FROM team_defense_weekly
            WHERE team = ? AND season_type = 'REG'
            ORDER BY season, week
            """,
            [team],
        )
    fp_expr = fantasy_points_sql_expr(preset)
    stats = sql_player_stat_select()
    return _fetch_df(
        conn,
        f"""
        SELECT season, week, team, opponent, position, games, {fp_expr} AS fantasy_points, {stats}
        FROM weekly_stats
        WHERE player_id = ? AND season_type = 'REG'
        ORDER BY season, week
        """,
        [entity_id],
    )


def player_seasons(
    conn: duckdb.DuckDBPyConnection,
    player_id: str,
    preset: str,
) -> pd.DataFrame:
    fp_expr = fantasy_points_sql_expr(preset)
    stats = sql_player_stat_select()
    return _fetch_df(
        conn,
        f"""
        SELECT
            player_name, season, position, teams, games,
            {fp_expr} AS fantasy_points,
            best_week, best_week_fp, best_week_scoring,
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
    fp_expr = fantasy_points_sql_expr(preset)
    stats = sql_player_stat_select()
    return _fetch_df(
        conn,
        f"""
        SELECT season, team, games, position, {fp_expr} AS fantasy_points, {stats}
        FROM season_team_stats
        WHERE player_id = ? AND season = ?
        ORDER BY team
        """,
        [player_id, season],
    )


def player_weekly(
    conn: duckdb.DuckDBPyConnection,
    player_id: str,
    season: int,
    preset: str,
) -> pd.DataFrame:
    fp_expr = fantasy_points_sql_expr(preset)
    stats = sql_player_stat_select()
    return _fetch_df(
        conn,
        f"""
        SELECT week, team, opponent, position, games, {fp_expr} AS fantasy_points, {stats}
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
    if min_games is None:
        min_games = get_min_games_default()

    fp_expr = fantasy_points_sql_expr(preset)
    stats = sql_stat_select()
    if season is not None:
        return _fetch_df(
            conn,
            f"""
            SELECT player_id, season, position, games, {fp_expr} AS fantasy_points, {stats}
            FROM season_stats WHERE season = ? AND games >= ?
            """,
            [season, min_games],
        )
    return _fetch_df(
        conn,
        f"""
        SELECT player_id, season, position, games, {fp_expr} AS fantasy_points, {stats}
        FROM season_stats WHERE games >= ?
        """,
        [min_games],
    )


def entity_display_label(conn: duckdb.DuckDBPyConnection, entity_id: str) -> str:
    """Human-readable name for a player or dst:TEAM entity."""
    if is_dst_entity(entity_id):
        from src.entities import dst_display_name, dst_team_from_entity

        return dst_display_name(dst_team_from_entity(entity_id))
    row = conn.execute(
        "SELECT player_name FROM players WHERE player_id = ?",
        [entity_id],
    ).fetchone()
    return str(row[0]) if row else entity_id


def entity_seasons_available(
    conn: duckdb.DuckDBPyConnection,
    entity_id: str,
    preset: str,
) -> list[int]:
    df = entity_seasons(conn, entity_id, preset)
    if df.empty or "season" not in df.columns:
        return []
    return sorted(int(s) for s in df["season"].dropna().unique())


def compare_shared_seasons(
    conn: duckdb.DuckDBPyConnection,
    entity_id_a: str,
    entity_id_b: str,
    preset: str,
) -> list[int]:
    """Season years where both entities have season-level data (newest first)."""
    a = set(entity_seasons_available(conn, entity_id_a, preset))
    b = set(entity_seasons_available(conn, entity_id_b, preset))
    return sorted(a & b, reverse=True)


def compare_union_seasons(
    conn: duckdb.DuckDBPyConnection,
    entity_id_a: str,
    entity_id_b: str,
    preset: str,
) -> list[int]:
    """Every season year either entity has data (newest first)."""
    a = set(entity_seasons_available(conn, entity_id_a, preset))
    b = set(entity_seasons_available(conn, entity_id_b, preset))
    return sorted(a | b, reverse=True)


def compare_entities(
    conn: duckdb.DuckDBPyConnection,
    entity_id_a: str,
    entity_id_b: str,
    preset: str,
    season: int | None = None,
    seasons: list[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df_a = entity_seasons(conn, entity_id_a, preset)
    df_b = entity_seasons(conn, entity_id_b, preset)
    if season is not None:
        yr = int(season)
        df_a = df_a[df_a["season"].astype(int) == yr]
        df_b = df_b[df_b["season"].astype(int) == yr]
    elif seasons:
        window = {int(s) for s in seasons}
        df_a = df_a[df_a["season"].astype(int).isin(window)]
        df_b = df_b[df_b["season"].astype(int).isin(window)]
    for frame, eid in ((df_a, entity_id_a), (df_b, entity_id_b)):
        if not frame.empty:
            frame["player_id"] = eid
    return df_a, df_b


def compare_players(
    conn: duckdb.DuckDBPyConnection,
    player_id_a: str,
    player_id_b: str,
    preset: str,
    season: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return compare_entities(conn, player_id_a, player_id_b, preset, season=season)


def search_players(
    conn: duckdb.DuckDBPyConnection,
    query: str = "",
    limit: int = 500,
) -> pd.DataFrame:
    entities = search_fantasy_entities(conn, query=query, limit=limit)
    if entities.empty:
        return entities
    players = entities[~entities["entity_id"].str.startswith("dst:")].copy()
    return players.rename(columns={"entity_id": "player_id"})


def search_fantasy_entities(
    conn: duckdb.DuckDBPyConnection,
    query: str = "",
    limit: int = 500,
) -> pd.DataFrame:
    """Players (player_id) and team defenses (dst:TEAM)."""
    if query.strip():
        pattern, team_codes = team_search_patterns(query)
        dst_clauses = ["team ILIKE ?"]
        params: list = [pattern, pattern]
        if team_codes:
            placeholders = ",".join(["?"] * len(team_codes))
            dst_clauses.append(f"team IN ({placeholders})")
            params.extend(team_codes)
        dst_where = " OR ".join(dst_clauses)
        params.append(limit)
        result = _fetch_df(
            conn,
            f"""
            SELECT entity_id, player_name, position, last_season FROM (
                SELECT
                    player_id AS entity_id,
                    player_name,
                    position,
                    last_season
                FROM players
                WHERE player_name ILIKE ?
                UNION ALL
                SELECT
                    'dst:' || team AS entity_id,
                    team AS player_name,
                    '{DST_POSITION}' AS position,
                    MAX(season) AS last_season
                FROM team_defense_season
                WHERE {dst_where}
                GROUP BY team
            )
            ORDER BY last_season DESC NULLS LAST, player_name
            LIMIT ?
            """,
            params,
        )
        return _label_dst_search_results(result)
    result = _fetch_df(
        conn,
        f"""
        SELECT entity_id, player_name, position, last_season FROM (
            SELECT player_id AS entity_id, player_name, position, last_season
            FROM players
            UNION ALL
            SELECT
                'dst:' || team AS entity_id,
                team AS player_name,
                '{DST_POSITION}' AS position,
                MAX(season) AS last_season
            FROM team_defense_season
            GROUP BY team
        )
        ORDER BY last_season DESC NULLS LAST, player_name
        LIMIT ?
        """,
        [limit],
    )
    return _label_dst_search_results(result)


def _label_dst_search_results(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "entity_id" not in df.columns:
        return df
    out = df.copy()
    mask = out["entity_id"].astype(str).str.startswith("dst:")
    if mask.any():
        out.loc[mask, "player_name"] = out.loc[mask, "player_name"].apply(dst_entity_display_name)
    return out


def teams_for_season(conn: duckdb.DuckDBPyConnection, season: int) -> list[str]:
    return teams_for_seasons(conn, [season])


def teams_for_seasons(conn: duckdb.DuckDBPyConnection, seasons: list[int]) -> list[str]:
    if not seasons:
        return []
    placeholders = ",".join(["?"] * len(seasons))
    rows = conn.execute(
        f"""
        SELECT DISTINCT team FROM (
            SELECT team FROM season_team_stats WHERE season IN ({placeholders})
            UNION
            SELECT team FROM team_defense_season WHERE season IN ({placeholders})
        ) ORDER BY team
        """,
        [*seasons, *seasons],
    ).fetchall()
    return [str(r[0]) for r in rows]
