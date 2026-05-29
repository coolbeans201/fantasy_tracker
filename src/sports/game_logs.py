"""Per-game stat rows for sport profiles."""

from __future__ import annotations

import duckdb
import pandas as pd

GAME_TABLES: dict[str, str] = {
    "nba": "nba_player_game_stats",
    "nhl": "nhl_player_game_stats",
    "mlb": "mlb_player_game_stats",
}

MLB_LOG_HITTING = "hitting"
MLB_LOG_PITCHING = "pitching"
NHL_LOG_SKATER = "skater"
NHL_LOG_GOALIE = "goalie"

# MLB regular season is at most 162 games per player; use for sanity checks in UI.
MLB_MAX_REGULAR_GAMES = 162


def _table_exists(conn: duckdb.DuckDBPyConnection, table: str) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE lower(table_name) = lower(?)
            LIMIT 1
            """,
            [table],
        ).fetchone()
        return row is not None
    except duckdb.Error:
        return False


def order_game_log_by_date(df: pd.DataFrame) -> pd.DataFrame:
    """Sort rows chronologically and set game_index 1..n per player."""
    if df.empty:
        return df
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    sort_date = pd.to_datetime(out.get("game_date"), errors="coerce")
    out["_sort_date"] = sort_date
    if "player_id" in out.columns:
        out = out.sort_values(
            ["player_id", "_sort_date", "game_id"],
            na_position="last",
        )
        out["game_index"] = out.groupby("player_id", sort=False).cumcount() + 1
    else:
        out = out.sort_values(["_sort_date", "game_id"], na_position="last")
        out["game_index"] = range(1, len(out) + 1)
    return out.drop(columns=["_sort_date"])


def load_player_game_log(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    player_id: str,
    season: int,
) -> pd.DataFrame | None:
    """Return game log for one player-season, or None if table not present."""
    table = GAME_TABLES.get(str(sport_id).strip().lower())
    if not table or not _table_exists(conn, table):
        return None
    df = conn.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE player_id = ? AND season = ?
        ORDER BY game_date NULLS LAST, game_index NULLS LAST
        """,
        [str(player_id).strip(), int(season)],
    ).df()
    if df.empty:
        return df
    df.columns = [str(c).lower() for c in df.columns]
    if "fantasy_points_espn" in df.columns and "fantasy_points" not in df.columns:
        df["fantasy_points"] = df["fantasy_points_espn"]
    sid = str(sport_id).strip().lower()
    if sid == "mlb":
        df = enrich_mlb_game_log_rows(df)
    elif sid == "nhl":
        df = enrich_nhl_game_log_rows(df)
    return order_game_log_by_date(df)


def mlb_two_way_season(
    conn: duckdb.DuckDBPyConnection,
    player_id: str,
    season: int,
) -> bool:
    """True when season stats include both hitter and pitcher stints."""
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT position
            FROM mlb_player_season_stats
            WHERE player_id = ? AND season = ?
            """,
            [str(player_id).strip(), int(season)],
        ).fetchall()
    except duckdb.Error:
        return False
    if not rows:
        return False
    from src.sports.mlb.positions import is_pitcher_position

    has_pitcher = any(is_pitcher_position(r[0]) for r in rows)
    has_hitter = any(not is_pitcher_position(r[0]) for r in rows if r[0])
    return has_pitcher and has_hitter


def mlb_two_way_career(
    conn: duckdb.DuckDBPyConnection,
    player_id: str,
) -> bool:
    """True when any ingested season has both hitter and pitcher stints."""
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT season, position
            FROM mlb_player_season_stats
            WHERE player_id = ?
            """,
            [str(player_id).strip()],
        ).fetchall()
    except duckdb.Error:
        return False
    if not rows:
        return False
    from src.sports.mlb.positions import is_pitcher_position

    by_season: dict[int, set[bool]] = {}
    for season, pos in rows:
        if pos is None:
            continue
        yr = int(season)
        bucket = by_season.setdefault(yr, set())
        bucket.add(is_pitcher_position(pos))
    for flags in by_season.values():
        if True in flags and False in flags:
            return True
    return False


def enrich_mlb_game_log_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure ``log_type`` is usable: reclassify rows from box-score columns when
    migrated data tagged everything as hitting.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    if "log_type" not in out.columns:
        out["log_type"] = MLB_LOG_HITTING

    ip = _numeric_col(out, "innings_pitched").fillna(0)
    runs = _numeric_col(out, "runs")
    hrs = _numeric_col(out, "home_runs").fillna(0)
    k_bat = _numeric_col(out, "strikeouts_bat").fillna(0)

    pitch_mask = ip > 0
    hit_mask = runs.notna() | (hrs > 0) | (k_bat > 0) | (runs.fillna(0) > 0)

    if pitch_mask.any():
        out.loc[pitch_mask, "log_type"] = MLB_LOG_PITCHING
    if hit_mask.any():
        out.loc[hit_mask, "log_type"] = MLB_LOG_HITTING

    return out


def _numeric_col(df: pd.DataFrame, name: str) -> pd.Series:
    """Per-row numeric series; missing columns become all-NA (never a scalar)."""
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce")
    return pd.Series(pd.NA, index=df.index, dtype="Float64")


def mlb_game_log_types_present(df: pd.DataFrame) -> set[str]:
    """Distinct ``log_type`` values after enrichment (may be empty)."""
    if df is None or df.empty:
        return set()
    work = enrich_mlb_game_log_rows(df)
    if "log_type" not in work.columns:
        return set()
    values = work["log_type"].astype(str).str.strip().str.lower()
    return {v for v in values if v and v not in {"nan", "none", "<na>"}}


def mlb_default_game_log_type(
    detail_rows: pd.DataFrame,
    games: pd.DataFrame,
    *,
    primary_position: str | None,
) -> str:
    """Default game-log cohort from primary season role, then ingested log types."""
    from src.sports.mlb.positions import is_pitcher_position

    present = mlb_game_log_types_present(games)
    pitcher_view = is_pitcher_position(primary_position)

    if present == {MLB_LOG_PITCHING}:
        return MLB_LOG_PITCHING
    if present == {MLB_LOG_HITTING}:
        # Legacy ingests tagged all rows as hitting; trust the season role.
        return MLB_LOG_PITCHING if pitcher_view else MLB_LOG_HITTING
    if not present:
        return MLB_LOG_PITCHING if pitcher_view else MLB_LOG_HITTING

    return MLB_LOG_PITCHING if pitcher_view else MLB_LOG_HITTING


def count_distinct_games(df: pd.DataFrame) -> int:
    """Unique games in a log (not row count — two-way players have 2 rows per game)."""
    if df is None or df.empty or "game_id" not in df.columns:
        return 0
    ids = df["game_id"].astype(str).str.strip()
    ids = ids[ids.ne("") & ids.str.lower().ne("nan")]
    return int(ids.nunique())


def mlb_position_for_game_log_type(log_type: str) -> str:
    """Display stat columns for a game-log cohort."""
    return "SP" if str(log_type).strip().lower() == MLB_LOG_PITCHING else "DH"


def enrich_nhl_game_log_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure ``log_type`` and infer goalie rows from saves/GA when legacy cache lacks type."""
    if df is None or df.empty:
        return df
    out = df.copy()
    if "log_type" not in out.columns:
        out["log_type"] = NHL_LOG_SKATER
    saves = _numeric_col(out, "saves").fillna(0)
    ga = _numeric_col(out, "goals_against").fillna(0)
    goalie_mask = saves.gt(0) | ga.gt(0)
    if goalie_mask.any():
        out.loc[goalie_mask, "log_type"] = NHL_LOG_GOALIE
    skater_mask = (
        _numeric_col(out, "goals").fillna(0).gt(0)
        | _numeric_col(out, "assists").fillna(0).gt(0)
        | _numeric_col(out, "shots").fillna(0).gt(0)
    )
    if skater_mask.any():
        out.loc[skater_mask, "log_type"] = NHL_LOG_SKATER
    return out


def filter_game_log_for_profile(
    df: pd.DataFrame,
    sport_id: str,
    position: str | None,
    *,
    log_type: str | None = None,
) -> pd.DataFrame:
    """
    Keep rows relevant to the profile role (MLB hitting vs pitching; NHL skater vs goalie).
    """
    if df is None or df.empty:
        return df
    sid = str(sport_id).strip().lower()

    if sid == "nhl":
        from src.sports.nhl.positions import is_goalie_position

        work = enrich_nhl_game_log_rows(df)
        want = str(log_type or "").strip().lower()
        if not want:
            want = NHL_LOG_GOALIE if is_goalie_position(position) else NHL_LOG_SKATER
        if "log_type" in work.columns:
            filtered = work[work["log_type"].astype(str).str.lower() == want]
            if not filtered.empty:
                return filtered.reset_index(drop=True)
        if is_goalie_position(position):
            mask = _numeric_col(work, "saves").fillna(0) > 0
            if not mask.any():
                mask = _numeric_col(work, "goals_against").fillna(0) > 0
            if mask.any():
                return work[mask].reset_index(drop=True)
        return work.reset_index(drop=True)

    if sid != "mlb":
        return df

    from src.sports.mlb.positions import is_pitcher_position

    work = enrich_mlb_game_log_rows(df)
    present = mlb_game_log_types_present(work)
    want = str(log_type or "").strip().lower()
    if not want:
        want = MLB_LOG_PITCHING if is_pitcher_position(position) else MLB_LOG_HITTING

    if "log_type" in work.columns:
        filtered = work[work["log_type"].astype(str).str.lower() == want]
        if not filtered.empty:
            return filtered.reset_index(drop=True)

        # Legacy ingests tagged every row as hitting; keep pitcher rows for SP/RP profiles.
        if want == MLB_LOG_PITCHING and is_pitcher_position(position):
            ip_mask = _numeric_col(work, "innings_pitched").fillna(0) > 0
            if ip_mask.any():
                return work[ip_mask].reset_index(drop=True)
            if MLB_LOG_PITCHING not in present:
                return work.reset_index(drop=True)

        if want == MLB_LOG_HITTING and not is_pitcher_position(position):
            hit_mask = _numeric_col(work, "runs").notna() | (
                _numeric_col(work, "home_runs").fillna(0) > 0
            )
            if hit_mask.any():
                return work[hit_mask].reset_index(drop=True)
            if MLB_LOG_HITTING not in present or present == {MLB_LOG_HITTING}:
                if MLB_LOG_PITCHING not in present:
                    return work.reset_index(drop=True)

        return filtered.reset_index(drop=True)

    pitcher_view = is_pitcher_position(position)

    if pitcher_view:
        mask = _numeric_col(df, "innings_pitched").fillna(0) > 0
        if mask.any():
            return df[mask].reset_index(drop=True)
    else:
        mask = _numeric_col(df, "runs").notna() | (_numeric_col(df, "home_runs").fillna(0) > 0)
        if mask.any():
            return df[mask].reset_index(drop=True)
    return df
