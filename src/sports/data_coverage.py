"""Per-sport ingest coverage summaries for hub / diagnostics."""

from __future__ import annotations

import duckdb

from src.db.connection import list_sport_seasons
from src.db.queries import list_rankings_seasons, season_has_rankings
from src.rankings.fantasypros_limits import sport_draft_ecr_supported
from src.sports.player_seasons import stats_table

_GAME_LOG_TABLE = {
    "mlb": "mlb_player_game_stats",
    "nba": "nba_player_game_stats",
    "nhl": "nhl_player_game_stats",
}

_DRAFT_ECR_SPORTS = frozenset({"mlb", "nba", "nhl"})


def _distinct_seasons(conn: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> list[int]:
    try:
        if params:
            rows = conn.execute(sql, params).fetchall()
        else:
            rows = conn.execute(sql).fetchall()
    except duckdb.Error:
        return []
    out: list[int] = []
    for row in rows:
        if row and row[0] is not None:
            try:
                out.append(int(row[0]))
            except (TypeError, ValueError):
                continue
    return sorted(out, reverse=True)


def sport_data_coverage(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
) -> dict[str, object]:
    """Season lists for stats, game logs, and draft ECR (where applicable)."""
    sid = str(sport_id).strip().lower()
    stats_seasons = list_sport_seasons(conn, sid)
    if not stats_seasons:
        stats_seasons = _distinct_seasons(
            conn,
            f"SELECT DISTINCT season FROM {stats_table(sid)} ORDER BY season DESC",
        )
    gamelog_seasons: list[int] = []
    gl_table = _GAME_LOG_TABLE.get(sid)
    if gl_table:
        gamelog_seasons = _distinct_seasons(
            conn, f"SELECT DISTINCT season FROM {gl_table} ORDER BY season DESC"
        )

    draft_seasons: list[int] = []
    draft_ready: list[int] = []
    if sid in _DRAFT_ECR_SPORTS:
        draft_seasons = _distinct_seasons(
            conn,
            "SELECT DISTINCT season FROM ecr_draft WHERE sport = ? ORDER BY season DESC",
            [sid],
        )
        for year in draft_seasons:
            if season_has_rankings(conn, year, sport=sid):
                draft_ready.append(year)
    elif sid == "nfl":
        draft_seasons = list_rankings_seasons(conn)
        draft_ready = [y for y in draft_seasons if season_has_rankings(conn, y)]

    stats_without_ecr = sorted(
        (
            year
            for year in set(stats_seasons) - set(draft_ready)
            if sport_draft_ecr_supported(sid, year)
        ),
        reverse=True,
    )
    draft_ecr_unsupported_seasons = sorted(
        (year for year in stats_seasons if not sport_draft_ecr_supported(sid, year)),
        reverse=True,
    )

    return {
        "sport_id": sid,
        "stats_table": stats_table(sid),
        "stats_seasons": stats_seasons,
        "gamelog_seasons": gamelog_seasons,
        "draft_ecr_seasons": draft_seasons,
        "draft_ecr_ready_seasons": draft_ready,
        "stats_without_draft_ecr": stats_without_ecr,
        "draft_ecr_unsupported_seasons": draft_ecr_unsupported_seasons,
        "latest_stats_season": stats_seasons[0] if stats_seasons else None,
    }
