"""Roll up per-game logs into fantasy weeks (Monday–Sunday)."""

from __future__ import annotations

import duckdb
import pandas as pd

from src.db.queries import load_ecr_weekly
from src.sports.game_logs import GAME_TABLES, filter_game_log_for_profile
from src.sports.peer_positions import positions_for_peer_grouping
from src.sports.mlb.positions import is_pitcher_position


def _monday_week_start(series: pd.Series) -> pd.Series:
    """Monday 00:00 of the calendar week containing each game_date."""
    dates = pd.to_datetime(series, errors="coerce")
    monday = dates.dt.normalize() - pd.to_timedelta(dates.dt.dayofweek, unit="D")
    return monday.dt.date


def _fp_week_from_monday(monday_dates: pd.Series) -> pd.Series:
    """Map week_start to 1-based week index within the season (chronological)."""
    uniq = sorted({d for d in monday_dates.dropna().unique()})
    order = {d: i + 1 for i, d in enumerate(uniq)}
    return monday_dates.map(order)


def rollup_game_log_to_weeks(
    games: pd.DataFrame,
    sport_id: str,
    *,
    log_type: str | None = None,
) -> pd.DataFrame:
    """
    Aggregate game rows to (player_id, season, week, position).

    ``week`` follows chronological Monday buckets in the season (for display);
    join weekly ECR on FantasyPros ``week`` index separately when ingested.
    """
    if games.empty:
        return pd.DataFrame()

    sid = str(sport_id).strip().lower()
    work = games.copy()
    work.columns = [str(c).lower() for c in work.columns]
    if "game_date" not in work.columns:
        return pd.DataFrame()

    fp_col = "fantasy_points"
    if fp_col not in work.columns and "fantasy_points_espn" in work.columns:
        work[fp_col] = pd.to_numeric(work["fantasy_points_espn"], errors="coerce")
    if fp_col not in work.columns:
        return pd.DataFrame()

    if "position" in work.columns:
        work["position"] = work["position"].apply(
            lambda p: positions_for_peer_grouping(sid, p) if p is not None else p
        )

    if log_type and sid in ("mlb", "nhl"):
        work = filter_game_log_for_profile(work, sid, None, log_type=log_type)

    work["week_start"] = _monday_week_start(work["game_date"])
    work = work.dropna(subset=["week_start"])
    if work.empty:
        return pd.DataFrame()

    work["week"] = _fp_week_from_monday(work["week_start"])
    work["week_end"] = pd.to_datetime(work["week_start"]) + pd.Timedelta(days=6)
    work["week_end"] = work["week_end"].dt.date

    group_cols = ["player_id", "season", "week", "position", "week_start", "week_end"]
    grouped = (
        work.groupby(group_cols, dropna=False)
        .agg(fantasy_points=(fp_col, "sum"), games=(fp_col, "size"))
        .reset_index()
    )
    grouped["sport"] = sid
    return grouped


def _ecr_role_key(sport_id: str, position: str | None) -> str:
    sid = str(sport_id).strip().lower()
    if sid == "mlb":
        return "pitcher" if is_pitcher_position(position) else "hitter"
    return str(position or "")


def remap_player_week_stats_to_ecr_weeks(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
) -> int:
    """
    Align calendar week indices to FantasyPros week numbers per player/role.

    Maps the i-th chronological Monday bucket to the i-th FP week present in ECR.
    """
    sid = str(sport_id).strip().lower()
    stats = conn.execute(
        """
        SELECT sport, player_id, season, week, position, fantasy_points, games,
               week_start, week_end
        FROM player_week_stats
        WHERE sport = ? AND season = ?
        """,
        [sid, int(season)],
    ).df()
    if stats.empty:
        return 0

    ecr = load_ecr_weekly(conn, int(season), sport=sid)
    if ecr.empty:
        return 0

    ecr = ecr.copy()
    ecr["_role"] = ecr["position"].map(lambda p: _ecr_role_key(sid, p))
    stats = stats.copy()
    stats["_role"] = stats["position"].map(lambda p: _ecr_role_key(sid, p))

    out_parts: list[pd.DataFrame] = []
    for (player_id, role), grp in stats.groupby(["player_id", "_role"], dropna=False):
        cal = grp.sort_values("week_start").copy()
        fp_weeks = sorted(
            ecr.loc[
                (ecr["player_id"].astype(str) == str(player_id)) & (ecr["_role"] == role),
                "week",
            ]
            .astype(int)
            .unique()
        )
        if fp_weeks:
            new_weeks = []
            for i, _row in enumerate(cal.itertuples()):
                new_weeks.append(fp_weeks[i] if i < len(fp_weeks) else int(cal.iloc[i]["week"]))
            cal["week"] = new_weeks
        out_parts.append(cal.drop(columns=["_role"], errors="ignore"))

    if not out_parts:
        return 0

    remapped = pd.concat(out_parts, ignore_index=True)
    conn.execute(
        "DELETE FROM player_week_stats WHERE sport = ? AND season = ?",
        [sid, int(season)],
    )
    cols = [
        "sport",
        "player_id",
        "season",
        "week",
        "position",
        "fantasy_points",
        "games",
        "week_start",
        "week_end",
    ]
    subset = remapped[cols].drop_duplicates(
        subset=["sport", "player_id", "season", "week", "position"],
        keep="first",
    )
    conn.register("_pws_remap", subset)
    cols_sql = ", ".join(cols)
    conn.execute(
        f"INSERT INTO player_week_stats ({cols_sql}) SELECT {cols_sql} FROM _pws_remap"
    )
    conn.unregister("_pws_remap")
    return len(subset)


def build_player_week_stats_for_season(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
    *,
    replace: bool = True,
) -> int:
    """Persist Monday–Sunday rollups for all players with game logs in a season."""
    sid = str(sport_id).strip().lower()
    table = GAME_TABLES.get(sid)
    if not table:
        return 0

    try:
        games = conn.execute(
            f"SELECT * FROM {table} WHERE season = ?",
            [int(season)],
        ).df()
    except duckdb.Error:
        return 0

    if games.empty:
        return 0

    games.columns = [str(c).lower() for c in games.columns]

    if sid == "mlb":
        from src.sports.game_logs import MLB_LOG_HITTING, MLB_LOG_PITCHING

        parts = []
        for log_type in (MLB_LOG_HITTING, MLB_LOG_PITCHING):
            chunk = rollup_game_log_to_weeks(games, sid, log_type=log_type)
            if not chunk.empty:
                parts.append(chunk)
        frame = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    elif sid == "nhl":
        from src.sports.game_logs import NHL_LOG_GOALIE, NHL_LOG_SKATER

        parts = []
        for log_type in (NHL_LOG_SKATER, NHL_LOG_GOALIE):
            chunk = rollup_game_log_to_weeks(games, sid, log_type=log_type)
            if not chunk.empty:
                parts.append(chunk)
        frame = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    else:
        frame = rollup_game_log_to_weeks(games, sid)

    if frame.empty:
        return 0

    if replace:
        conn.execute(
            "DELETE FROM player_week_stats WHERE sport = ? AND season = ?",
            [sid, int(season)],
        )

    cols = [
        "sport",
        "player_id",
        "season",
        "week",
        "position",
        "fantasy_points",
        "games",
        "week_start",
        "week_end",
    ]
    subset = frame[cols].drop_duplicates(
        subset=["sport", "player_id", "season", "week", "position"],
        keep="first",
    )
    conn.register("_pws_tmp", subset)
    cols_sql = ", ".join(cols)
    conn.execute(
        f"INSERT INTO player_week_stats ({cols_sql}) SELECT {cols_sql} FROM _pws_tmp"
    )
    conn.unregister("_pws_tmp")
    remap_player_week_stats_to_ecr_weeks(conn, sid, season)
    return len(subset)
