"""Season years available per player (MLB / NBA / NHL season tables)."""

from __future__ import annotations

import duckdb

SPORT_STATS_TABLE: dict[str, str] = {
    "mlb": "mlb_player_season_stats",
    "nba": "nba_player_season_stats",
    "nhl": "nhl_player_season_stats",
}


def stats_table(sport_id: str) -> str:
    table = SPORT_STATS_TABLE.get(str(sport_id).strip().lower())
    if not table:
        raise ValueError(f"No season stats table for sport: {sport_id}")
    return table


def player_seasons_available(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    player_id: str,
) -> list[int]:
    """Distinct ingested seasons for this player (newest first)."""
    table = stats_table(sport_id)
    rows = conn.execute(
        f"""
        SELECT DISTINCT season
        FROM {table}
        WHERE player_id = ?
        ORDER BY season DESC
        """,
        [str(player_id).strip()],
    ).fetchall()
    return [int(r[0]) for r in rows if r[0] is not None]


def compare_shared_seasons(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    player_id_a: str,
    player_id_b: str,
) -> list[int]:
    a = set(player_seasons_available(conn, sport_id, player_id_a))
    b = set(player_seasons_available(conn, sport_id, player_id_b))
    return sorted(a & b, reverse=True)


def compare_union_seasons(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    player_id_a: str,
    player_id_b: str,
) -> list[int]:
    a = set(player_seasons_available(conn, sport_id, player_id_a))
    b = set(player_seasons_available(conn, sport_id, player_id_b))
    return sorted(a | b, reverse=True)


def distinct_teams_for_seasons(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    seasons: list[int],
) -> list[str]:
    """Distinct team abbreviations for one or more seasons (sorted)."""
    if not seasons:
        return []
    table = stats_table(sport_id)
    placeholders = ", ".join("?" * len(seasons))
    rows = conn.execute(
        f"""
        SELECT DISTINCT team
        FROM {table}
        WHERE season IN ({placeholders})
          AND team IS NOT NULL AND TRIM(CAST(team AS VARCHAR)) != ''
        ORDER BY team
        """,
        [int(s) for s in seasons],
    ).fetchall()
    return [str(r[0]).strip() for r in rows if r[0] is not None]
