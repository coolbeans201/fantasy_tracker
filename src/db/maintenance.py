"""Database maintenance: backfill games played and player display names."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.scoring.special import DST_FP_COLUMN, apply_dst_points
from src.team_dst_columns import (
    DST_STAT_COLUMNS,
    attach_opponent_allowed_stats,
    build_team_dst_season_aggregates,
)
from src.text_encoding import normalize_unicode_text


def _player_id_column(players_df) -> str | None:
    for col in ("gsis_id", "player_id", "nfl_id"):
        if col in players_df.columns:
            return col
    return None


def rebuild_players_table(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Rebuild players from all season_stats rows (latest season per player).
    Bulk ingest runs one season at a time; replacing players from only the last
    batch dropped everyone not in that season (e.g. retired Andrew Luck).
    """
    rows = conn.execute("SELECT COUNT(*) FROM season_stats").fetchone()[0]
    if rows == 0:
        return

    conn.execute("DELETE FROM players WHERE sport = 'nfl'")
    conn.execute(
        """
        INSERT INTO players (sport, player_id, player_name, position, last_season)
        SELECT 'nfl', player_id, player_name, position, season AS last_season
        FROM season_stats
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY player_id ORDER BY season DESC
        ) = 1
        """
    )


def players_table_needs_rebuild(conn: duckdb.DuckDBPyConnection) -> bool:
    """True when players is missing IDs that exist in season_stats."""
    season_count = conn.execute(
        "SELECT COUNT(DISTINCT player_id) FROM season_stats"
    ).fetchone()[0]
    if season_count == 0:
        return False
    players_count = conn.execute(
        "SELECT COUNT(*) FROM players WHERE sport = 'nfl'"
    ).fetchone()[0]
    return players_count < season_count


def refresh_player_display_names(conn: duckdb.DuckDBPyConnection) -> None:
    """Backfill full display names from nflverse players master file."""
    if conn.execute("SELECT COUNT(*) FROM weekly_stats").fetchone()[0] == 0:
        return

    abbreviated = conn.execute(
        """
        SELECT COUNT(*) FROM season_stats
        WHERE regexp_matches(player_name, '^[A-Z]\\.[A-Za-z]')
        """
    ).fetchone()[0]
    if abbreviated == 0:
        return

    import nflreadpy as nfl

    master = nfl.load_players()
    if hasattr(master, "to_pandas"):
        master = master.to_pandas()

    id_col = _player_id_column(master)
    if id_col is None or "display_name" not in master.columns:
        return

    mapping = (
        master[[id_col, "display_name"]]
        .dropna()
        .rename(columns={id_col: "player_id", "display_name": "player_name"})
    )
    mapping["player_id"] = mapping["player_id"].astype(str).str.strip()
    mapping["player_name"] = mapping["player_name"].astype(str).str.strip()
    mapping = mapping[mapping["player_name"].str.len() > 0].drop_duplicates("player_id")

    if mapping.empty:
        return

    conn.register("_player_name_map", mapping)
    for table in ("weekly_stats", "season_stats", "season_team_stats", "players"):
        conn.execute(
            f"""
            UPDATE {table} AS t
            SET player_name = m.player_name
            FROM _player_name_map AS m
            WHERE t.player_id = m.player_id
            """
        )
    conn.unregister("_player_name_map")


def recompute_games_played(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Set games = distinct regular-season weeks with stats.
    Fixes legacy ingests that summed a missing nflverse `games` column to 0.
    """
    weekly_rows = conn.execute("SELECT COUNT(*) FROM weekly_stats").fetchone()[0]
    if weekly_rows == 0:
        return

    mismatch = conn.execute(
        """
        SELECT COUNT(*)
        FROM season_stats AS s
        INNER JOIN (
            SELECT
                player_id,
                season,
                CAST(COUNT(DISTINCT week) AS INTEGER) AS cnt
            FROM weekly_stats
            WHERE season_type = 'REG'
            GROUP BY player_id, season
        ) AS w
          ON s.player_id = w.player_id AND s.season = w.season
        WHERE COALESCE(s.games, 0) != w.cnt
        """
    ).fetchone()[0]
    if mismatch == 0:
        return

    conn.execute(
        """
        UPDATE season_stats AS s
        SET games = w.cnt
        FROM (
            SELECT
                player_id,
                season,
                CAST(COUNT(DISTINCT week) AS INTEGER) AS cnt
            FROM weekly_stats
            WHERE season_type = 'REG'
            GROUP BY player_id, season
        ) AS w
        WHERE s.player_id = w.player_id AND s.season = w.season
        """
    )
    conn.execute(
        """
        UPDATE season_team_stats AS s
        SET games = w.cnt
        FROM (
            SELECT
                player_id,
                season,
                team,
                CAST(COUNT(DISTINCT week) AS INTEGER) AS cnt
            FROM weekly_stats
            WHERE season_type = 'REG'
            GROUP BY player_id, season, team
        ) AS w
        WHERE s.player_id = w.player_id
          AND s.season = w.season
          AND s.team = w.team
        """
    )


def _opponent_lookup_from_nflverse(raw: pd.DataFrame, *, team_level: bool) -> pd.DataFrame:
    """REG rows with join keys + opponent abbreviation."""
    if raw.empty or "opponent_team" not in raw.columns:
        return pd.DataFrame()

    frame = raw.copy()
    if hasattr(frame, "to_pandas"):
        frame = frame.to_pandas()

    if "season_type" in frame.columns:
        frame = frame[frame["season_type"] == "REG"]

    team_col = "team" if "team" in frame.columns else "recent_team"
    if team_col not in frame.columns:
        return pd.DataFrame()

    keys = ["season", "week", "season_type", team_col, "opponent_team"]
    if not team_level:
        if "player_id" not in frame.columns:
            return pd.DataFrame()
        keys = ["player_id", *keys]

    subset = frame[keys].drop_duplicates()
    subset = subset.rename(columns={team_col: "team", "opponent_team": "opponent"})
    subset["team"] = subset["team"].astype(str).str.strip()
    subset["opponent"] = subset["opponent"].astype(str).str.strip()
    subset = subset[subset["opponent"].str.len() > 0]
    return subset


def backfill_weekly_opponents(conn: duckdb.DuckDBPyConnection) -> None:
    """Fill opponent from nflverse for rows ingested before the column existed."""
    player_missing = conn.execute(
        """
        SELECT COUNT(*) FROM weekly_stats
        WHERE season_type = 'REG' AND opponent IS NULL
        """
    ).fetchone()[0]
    dst_missing = conn.execute(
        """
        SELECT COUNT(*) FROM team_defense_weekly
        WHERE season_type = 'REG' AND opponent IS NULL
        """
    ).fetchone()[0]
    if player_missing == 0 and dst_missing == 0:
        return

    import nflreadpy as nfl

    seasons = [
        int(row[0])
        for row in conn.execute(
            """
            SELECT DISTINCT season FROM weekly_stats
            UNION
            SELECT DISTINCT season FROM team_defense_weekly
            ORDER BY season
            """
        ).fetchall()
    ]
    if not seasons:
        return

    if player_missing:
        raw_players = nfl.load_player_stats(seasons)
        lookup = _opponent_lookup_from_nflverse(raw_players, team_level=False)
        if not lookup.empty:
            conn.register("_weekly_opp", lookup)
            conn.execute(
                """
                UPDATE weekly_stats AS w
                SET opponent = o.opponent
                FROM _weekly_opp AS o
                WHERE w.player_id = o.player_id
                  AND w.season = o.season
                  AND w.week = o.week
                  AND w.season_type = o.season_type
                  AND w.team = o.team
                  AND w.opponent IS NULL
                """
            )
            conn.unregister("_weekly_opp")

    if dst_missing:
        raw_teams = nfl.load_team_stats(seasons)
        lookup = _opponent_lookup_from_nflverse(raw_teams, team_level=True)
        if not lookup.empty:
            conn.register("_dst_weekly_opp", lookup)
            conn.execute(
                """
                UPDATE team_defense_weekly AS w
                SET opponent = o.opponent
                FROM _dst_weekly_opp AS o
                WHERE w.team = o.team
                  AND w.season = o.season
                  AND w.week = o.week
                  AND w.season_type = o.season_type
                  AND w.opponent IS NULL
                """
            )
            conn.unregister("_dst_weekly_opp")


def backfill_mlb_player_names(conn: duckdb.DuckDBPyConnection) -> None:
    """Fix MLB names stored with literal \\x UTF-8 escapes or Latin-1 mojibake."""
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM mlb_player_season_stats"
        ).fetchone()[0]
    except duckdb.Error:
        return
    if rows == 0:
        return

    names = conn.execute(
        """
        SELECT DISTINCT player_id, player_name
        FROM mlb_player_season_stats
        WHERE player_name LIKE '%\\x%'
           OR player_name LIKE '%Ã%'
           OR player_name LIKE '%\\u%'
        """
    ).df()
    if names.empty:
        return

    names["fixed_name"] = names["player_name"].map(normalize_unicode_text)
    changed = names[names["fixed_name"] != names["player_name"]]
    if changed.empty:
        return

    conn.register("_mlb_names", changed[["player_id", "fixed_name"]])
    conn.execute(
        """
        UPDATE mlb_player_season_stats AS s
        SET player_name = n.fixed_name
        FROM _mlb_names AS n
        WHERE s.player_id = n.player_id
        """
    )
    conn.unregister("_mlb_names")


def backfill_dst_points_allowed(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Fix D/ST points_allowed and yards_allowed (and fantasy_points_dst).
    PA from schedules; yards from opponent offensive totals in team stats.
    """
    try:
        total = conn.execute(
            """
            SELECT COUNT(*) FROM team_defense_weekly
            WHERE season_type = 'REG'
            """
        ).fetchone()[0]
        needs_fix = conn.execute(
            """
            SELECT COUNT(*) FROM team_defense_weekly
            WHERE season_type = 'REG'
              AND (COALESCE(points_allowed, 0) = 0 OR COALESCE(yards_allowed, 0) = 0)
            """
        ).fetchone()[0]
    except duckdb.Error:
        return

    if total == 0 or needs_fix == 0:
        return

    weekly = conn.execute(
        f"""
        SELECT team, season, week, season_type, opponent, games,
               {", ".join(DST_STAT_COLUMNS)}
        FROM team_defense_weekly
        WHERE season_type = 'REG'
        """
    ).df()
    if weekly.empty:
        return

    import nflreadpy as nfl

    seasons = sorted(int(s) for s in weekly["season"].dropna().unique())
    schedules = nfl.load_schedules(seasons)
    raw_teams = nfl.load_team_stats(seasons)
    fixed = apply_dst_points(
        attach_opponent_allowed_stats(weekly, schedules=schedules, team_stats=raw_teams)
    )
    if fixed.empty:
        return

    conn.register("_dst_pa", fixed)
    conn.execute(
        f"""
        UPDATE team_defense_weekly AS w
        SET points_allowed = f.points_allowed,
            yards_allowed = f.yards_allowed,
            {DST_FP_COLUMN} = f.{DST_FP_COLUMN}
        FROM _dst_pa AS f
        WHERE w.team = f.team
          AND w.season = f.season
          AND w.week = f.week
          AND w.season_type = f.season_type
        """
    )
    conn.unregister("_dst_pa")

    season_dst = build_team_dst_season_aggregates(fixed)
    if season_dst.empty:
        return

    placeholders = ", ".join("?" * len(seasons))
    conn.execute(
        f"DELETE FROM team_defense_season WHERE season IN ({placeholders})",
        seasons,
    )
    season_cols = [
        "team",
        "season",
        "games",
        *DST_STAT_COLUMNS,
        DST_FP_COLUMN,
        "best_week",
        "best_week_fp",
    ]
    for col in season_cols:
        if col not in season_dst.columns:
            season_dst[col] = pd.NA
    conn.register("_dst_season", season_dst[season_cols])
    conn.execute(
        f"""
        INSERT INTO team_defense_season ({", ".join(season_cols)})
        SELECT {", ".join(season_cols)} FROM _dst_season
        """
    )
    conn.unregister("_dst_season")


__all__ = [
    "backfill_dst_points_allowed",
    "backfill_mlb_player_names",
    "backfill_weekly_opponents",
    "players_table_needs_rebuild",
    "rebuild_players_table",
    "recompute_games_played",
    "refresh_player_display_names",
]
