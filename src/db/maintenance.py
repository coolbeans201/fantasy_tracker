"""Database maintenance: backfill games played and player display names."""

from __future__ import annotations

import duckdb


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

    conn.execute("DELETE FROM players")
    conn.execute(
        """
        INSERT INTO players (player_id, player_name, position, last_season)
        SELECT player_id, player_name, position, season AS last_season
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
    players_count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
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


__all__ = [
    "players_table_needs_rebuild",
    "rebuild_players_table",
    "recompute_games_played",
    "refresh_player_display_names",
]
