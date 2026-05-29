"""DDL for multi-sport shared dimensions and per-sport stat tables."""

from __future__ import annotations

import duckdb

MLB_PLAYER_SEASON_COLUMNS: tuple[str, ...] = (
    "player_id",
    "player_name",
    "season",
    "position",
    "team",
    "games",
    "plate_appearances",
    "runs",
    "home_runs",
    "rbi",
    "stolen_bases",
    "walks",
    "strikeouts_bat",
    "batting_avg",
    "wins",
    "strikeouts_pitch",
    "saves",
    "innings_pitched",
    "era",
    "whip",
    "fantasy_points_espn",
)

MLB_SEASON_DDL = """
CREATE TABLE IF NOT EXISTS mlb_ingest_manifest (
    season INTEGER PRIMARY KEY,
    ingested_at TIMESTAMP NOT NULL,
    row_count INTEGER
);

CREATE TABLE IF NOT EXISTS mlb_player_season_stats (
    player_id VARCHAR NOT NULL,
    player_name VARCHAR,
    season INTEGER NOT NULL,
    position VARCHAR NOT NULL,
    team VARCHAR,
    games INTEGER,
    plate_appearances DOUBLE DEFAULT 0,
    runs DOUBLE DEFAULT 0,
    home_runs DOUBLE DEFAULT 0,
    rbi DOUBLE DEFAULT 0,
    stolen_bases DOUBLE DEFAULT 0,
    walks DOUBLE DEFAULT 0,
    strikeouts_bat DOUBLE DEFAULT 0,
    batting_avg DOUBLE DEFAULT 0,
    wins DOUBLE DEFAULT 0,
    strikeouts_pitch DOUBLE DEFAULT 0,
    saves DOUBLE DEFAULT 0,
    innings_pitched DOUBLE DEFAULT 0,
    era DOUBLE DEFAULT 0,
    whip DOUBLE DEFAULT 0,
    fantasy_points_espn DOUBLE,
    PRIMARY KEY (player_id, season, position, team)
);

CREATE INDEX IF NOT EXISTS idx_mlb_season ON mlb_player_season_stats(season, position);
CREATE INDEX IF NOT EXISTS idx_mlb_season_team ON mlb_player_season_stats(season, team);
"""

NBA_SEASON_DDL = """
CREATE TABLE IF NOT EXISTS nba_ingest_manifest (
    season INTEGER PRIMARY KEY,
    ingested_at TIMESTAMP NOT NULL,
    row_count INTEGER
);

CREATE TABLE IF NOT EXISTS nba_player_season_stats (
    player_id VARCHAR NOT NULL,
    player_name VARCHAR,
    season INTEGER NOT NULL,
    position VARCHAR,
    team VARCHAR,
    games INTEGER,
    points DOUBLE DEFAULT 0,
    rebounds DOUBLE DEFAULT 0,
    assists DOUBLE DEFAULT 0,
    steals DOUBLE DEFAULT 0,
    blocks DOUBLE DEFAULT 0,
    turnovers DOUBLE DEFAULT 0,
    three_pointers DOUBLE DEFAULT 0,
    fantasy_points_espn DOUBLE,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX IF NOT EXISTS idx_nba_season ON nba_player_season_stats(season, position);
"""

NHL_PLAYER_SEASON_COLUMNS: tuple[str, ...] = (
    "player_id",
    "player_name",
    "season",
    "position",
    "team",
    "games",
    "goals",
    "assists",
    "points",
    "plus_minus",
    "shots",
    "hits",
    "blocks",
    "wins",
    "saves",
    "goals_against",
    "shutouts",
    "fantasy_points_espn",
)

NHL_SEASON_DDL = """
CREATE TABLE IF NOT EXISTS nhl_ingest_manifest (
    season INTEGER PRIMARY KEY,
    ingested_at TIMESTAMP NOT NULL,
    row_count INTEGER
);

CREATE TABLE IF NOT EXISTS nhl_player_season_stats (
    player_id VARCHAR NOT NULL,
    player_name VARCHAR,
    season INTEGER NOT NULL,
    position VARCHAR NOT NULL,
    team VARCHAR,
    games INTEGER,
    goals DOUBLE DEFAULT 0,
    assists DOUBLE DEFAULT 0,
    points DOUBLE DEFAULT 0,
    plus_minus DOUBLE DEFAULT 0,
    shots DOUBLE DEFAULT 0,
    hits DOUBLE DEFAULT 0,
    blocks DOUBLE DEFAULT 0,
    wins DOUBLE DEFAULT 0,
    saves DOUBLE DEFAULT 0,
    goals_against DOUBLE DEFAULT 0,
    shutouts DOUBLE DEFAULT 0,
    fantasy_points_espn DOUBLE,
    PRIMARY KEY (player_id, season, position, team)
);

CREATE INDEX IF NOT EXISTS idx_nhl_season ON nhl_player_season_stats(season, position);
CREATE INDEX IF NOT EXISTS idx_nhl_season_team ON nhl_player_season_stats(season, team);
"""

NBA_GAME_DDL = """
CREATE TABLE IF NOT EXISTS nba_player_game_stats (
    player_id VARCHAR NOT NULL,
    player_name VARCHAR,
    season INTEGER NOT NULL,
    game_id VARCHAR NOT NULL,
    game_date DATE,
    game_index INTEGER,
    team VARCHAR,
    opponent VARCHAR,
    points DOUBLE DEFAULT 0,
    rebounds DOUBLE DEFAULT 0,
    assists DOUBLE DEFAULT 0,
    steals DOUBLE DEFAULT 0,
    blocks DOUBLE DEFAULT 0,
    turnovers DOUBLE DEFAULT 0,
    three_pointers DOUBLE DEFAULT 0,
    fantasy_points_espn DOUBLE,
    PRIMARY KEY (player_id, season, game_id)
);

CREATE INDEX IF NOT EXISTS idx_nba_game_season ON nba_player_game_stats(season, player_id);
"""

NHL_PLAYER_GAME_COLUMNS: tuple[str, ...] = (
    "player_id",
    "player_name",
    "season",
    "game_id",
    "log_type",
    "game_date",
    "game_index",
    "team",
    "opponent",
    "goals",
    "assists",
    "points",
    "shots",
    "wins",
    "saves",
    "goals_against",
    "shutouts",
    "fantasy_points_espn",
)

NHL_GAME_DDL = """
CREATE TABLE IF NOT EXISTS nhl_player_game_stats (
    player_id VARCHAR NOT NULL,
    player_name VARCHAR,
    season INTEGER NOT NULL,
    game_id VARCHAR NOT NULL,
    log_type VARCHAR NOT NULL DEFAULT 'skater',
    game_date DATE,
    game_index INTEGER,
    team VARCHAR,
    opponent VARCHAR,
    goals DOUBLE DEFAULT 0,
    assists DOUBLE DEFAULT 0,
    points DOUBLE DEFAULT 0,
    shots DOUBLE DEFAULT 0,
    wins DOUBLE DEFAULT 0,
    saves DOUBLE DEFAULT 0,
    goals_against DOUBLE DEFAULT 0,
    shutouts DOUBLE DEFAULT 0,
    fantasy_points_espn DOUBLE,
    PRIMARY KEY (player_id, season, game_id, log_type)
);
"""

MLB_PLAYER_GAME_COLUMNS: tuple[str, ...] = (
    "player_id",
    "player_name",
    "season",
    "game_id",
    "log_type",
    "game_date",
    "game_index",
    "team",
    "opponent",
    "runs",
    "home_runs",
    "rbi",
    "stolen_bases",
    "walks",
    "strikeouts_bat",
    "wins",
    "strikeouts_pitch",
    "saves",
    "innings_pitched",
    "era",
    "fantasy_points_espn",
)

MLB_GAME_DDL = """
CREATE TABLE IF NOT EXISTS mlb_player_game_stats (
    player_id VARCHAR NOT NULL,
    player_name VARCHAR,
    season INTEGER NOT NULL,
    game_id VARCHAR NOT NULL,
    log_type VARCHAR NOT NULL DEFAULT 'hitting',
    game_date DATE,
    game_index INTEGER,
    team VARCHAR,
    opponent VARCHAR,
    runs DOUBLE DEFAULT 0,
    home_runs DOUBLE DEFAULT 0,
    rbi DOUBLE DEFAULT 0,
    stolen_bases DOUBLE DEFAULT 0,
    walks DOUBLE DEFAULT 0,
    strikeouts_bat DOUBLE DEFAULT 0,
    wins DOUBLE DEFAULT 0,
    strikeouts_pitch DOUBLE DEFAULT 0,
    saves DOUBLE DEFAULT 0,
    innings_pitched DOUBLE DEFAULT 0,
    era DOUBLE DEFAULT 0,
    fantasy_points_espn DOUBLE,
    PRIMARY KEY (player_id, season, game_id, log_type)
);
"""


def _mlb_table_exists(conn: duckdb.DuckDBPyConnection) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE lower(table_name) = 'mlb_player_season_stats'
            LIMIT 1
            """
        ).fetchone()
        return row is not None
    except duckdb.Error:
        return False


def _mlb_primary_key_columns(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """Return PK column names in order, or [] if unknown."""
    try:
        row = conn.execute(
            """
            SELECT constraint_column_names
            FROM duckdb_constraints()
            WHERE lower(table_name) = 'mlb_player_season_stats'
              AND constraint_type = 'PRIMARY KEY'
            LIMIT 1
            """
        ).fetchone()
        if row and row[0] is not None:
            raw = row[0]
            if isinstance(raw, (list, tuple)):
                return [str(c).lower() for c in raw]
            return [str(raw).lower()]
    except duckdb.Error:
        pass
    try:
        rows = conn.execute(
            """
            SELECT lower(k.column_name) AS column_name
            FROM information_schema.table_constraints AS t
            JOIN information_schema.key_column_usage AS k
              ON t.constraint_name = k.constraint_name
             AND t.table_schema = k.table_schema
             AND t.table_name = k.table_name
            WHERE lower(t.table_name) = 'mlb_player_season_stats'
              AND t.constraint_type = 'PRIMARY KEY'
            ORDER BY k.ordinal_position
            """
        ).fetchall()
        if rows:
            return [str(r[0]).lower() for r in rows]
    except duckdb.Error:
        pass
    return []


def _mlb_has_column(conn: duckdb.DuckDBPyConnection, col_name: str) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE lower(table_name) = 'mlb_player_season_stats'
              AND lower(column_name) = ?
            LIMIT 1
            """,
            [str(col_name).strip().lower()],
        ).fetchone()
        return row is not None
    except duckdb.Error:
        return False


def _migrate_mlb_player_season_stats(conn: duckdb.DuckDBPyConnection) -> None:
    """Recreate MLB table unless PK is (player_id, season, position, team)."""
    if not _mlb_table_exists(conn):
        return
    names = _mlb_primary_key_columns(conn)
    has_pa = _mlb_has_column(conn, "plate_appearances")
    if names == ["player_id", "season", "position", "team"] and has_pa:
        return
    try:
        existing = conn.execute("SELECT * FROM mlb_player_season_stats").df()
    except duckdb.Error:
        existing = None
    conn.execute("DROP TABLE mlb_player_season_stats")
    conn.execute(
        """
        CREATE TABLE mlb_player_season_stats (
            player_id VARCHAR NOT NULL,
            player_name VARCHAR,
            season INTEGER NOT NULL,
            position VARCHAR NOT NULL,
            team VARCHAR,
            games INTEGER,
            plate_appearances DOUBLE DEFAULT 0,
            runs DOUBLE DEFAULT 0,
            home_runs DOUBLE DEFAULT 0,
            rbi DOUBLE DEFAULT 0,
            stolen_bases DOUBLE DEFAULT 0,
            walks DOUBLE DEFAULT 0,
            strikeouts_bat DOUBLE DEFAULT 0,
            batting_avg DOUBLE DEFAULT 0,
            wins DOUBLE DEFAULT 0,
            strikeouts_pitch DOUBLE DEFAULT 0,
            saves DOUBLE DEFAULT 0,
            innings_pitched DOUBLE DEFAULT 0,
            era DOUBLE DEFAULT 0,
            whip DOUBLE DEFAULT 0,
            fantasy_points_espn DOUBLE,
            PRIMARY KEY (player_id, season, position, team)
        )
        """
    )
    if existing is not None and not existing.empty:
        existing.columns = [str(c).lower() for c in existing.columns]
        if "position" not in existing.columns:
            existing["position"] = "H"
        if "team" not in existing.columns:
            existing["team"] = "UNK"
        if "plate_appearances" not in existing.columns:
            existing["plate_appearances"] = 0.0
        from src.sports.mlb.teams import normalize_mlb_team

        existing["team"] = existing["team"].map(normalize_mlb_team)
        conn.register("_mlb_mig", existing)
        cols = ", ".join(MLB_PLAYER_SEASON_COLUMNS)
        conn.execute(
            f"""
            INSERT INTO mlb_player_season_stats ({cols})
            SELECT {cols} FROM _mlb_mig
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY player_id, season, position, team
                ORDER BY games DESC NULLS LAST
            ) = 1
            """
        )
        conn.unregister("_mlb_mig")


def ensure_mlb_player_season_stats_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply MLB DDL and rebuild the stats table if the primary key is outdated."""
    conn.execute(MLB_SEASON_DDL)
    _migrate_mlb_player_season_stats(conn)


def _mlb_game_table_exists(conn: duckdb.DuckDBPyConnection) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE lower(table_name) = 'mlb_player_game_stats'
            LIMIT 1
            """
        ).fetchone()
        return row is not None
    except duckdb.Error:
        return False


def _mlb_game_primary_key_columns(conn: duckdb.DuckDBPyConnection) -> list[str]:
    try:
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.key_column_usage
            WHERE lower(table_name) = 'mlb_player_game_stats'
            ORDER BY ordinal_position
            """
        ).fetchall()
        return [str(r[0]).lower() for r in rows]
    except duckdb.Error:
        return []


def _mlb_game_has_column(conn: duckdb.DuckDBPyConnection, name: str) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE lower(table_name) = 'mlb_player_game_stats'
              AND lower(column_name) = lower(?)
            LIMIT 1
            """,
            [name],
        ).fetchone()
        return row is not None
    except duckdb.Error:
        return False


def _migrate_mlb_player_game_stats(conn: duckdb.DuckDBPyConnection) -> None:
    """Recreate MLB game log table when PK or stat columns are outdated."""
    if not _mlb_game_table_exists(conn):
        return
    pk = _mlb_game_primary_key_columns(conn)
    needs_rebuild = pk != ["player_id", "season", "game_id", "log_type"] or not _mlb_game_has_column(
        conn, "runs"
    )
    if not needs_rebuild:
        return
    try:
        existing = conn.execute("SELECT * FROM mlb_player_game_stats").df()
    except duckdb.Error:
        existing = None
    conn.execute("DROP TABLE mlb_player_game_stats")
    conn.execute(MLB_GAME_DDL)
    if existing is not None and not existing.empty:
        existing.columns = [str(c).lower() for c in existing.columns]
        if "log_type" not in existing.columns:
            existing["log_type"] = "hitting"
        for col in MLB_PLAYER_GAME_COLUMNS:
            if col not in existing.columns:
                existing[col] = None
        conn.register("_mlb_game_mig", existing)
        cols = ", ".join(MLB_PLAYER_GAME_COLUMNS)
        conn.execute(
            f"""
            INSERT INTO mlb_player_game_stats ({cols})
            SELECT {cols} FROM _mlb_game_mig
            """
        )
        conn.unregister("_mlb_game_mig")


def ensure_mlb_player_game_stats_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply MLB game-log DDL and migrate legacy tables."""
    conn.execute(MLB_GAME_DDL)
    _migrate_mlb_player_game_stats(conn)


def _nhl_table_exists(conn: duckdb.DuckDBPyConnection) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE lower(table_name) = 'nhl_player_season_stats'
            LIMIT 1
            """
        ).fetchone()
        return row is not None
    except duckdb.Error:
        return False


def _nhl_primary_key_columns(conn: duckdb.DuckDBPyConnection) -> list[str]:
    try:
        row = conn.execute(
            """
            SELECT constraint_column_names
            FROM duckdb_constraints()
            WHERE lower(table_name) = 'nhl_player_season_stats'
              AND constraint_type = 'PRIMARY KEY'
            LIMIT 1
            """
        ).fetchone()
        if row and row[0] is not None:
            raw = row[0]
            if isinstance(raw, (list, tuple)):
                return [str(c).lower() for c in raw]
            return [str(raw).lower()]
    except duckdb.Error:
        pass
    return []


def _migrate_nhl_player_season_stats(conn: duckdb.DuckDBPyConnection) -> None:
    """Recreate NHL table unless PK is (player_id, season, position, team)."""
    if not _nhl_table_exists(conn):
        return
    names = _nhl_primary_key_columns(conn)
    if names == ["player_id", "season", "position", "team"]:
        return
    try:
        existing = conn.execute("SELECT * FROM nhl_player_season_stats").df()
    except duckdb.Error:
        existing = None
    conn.execute("DROP TABLE nhl_player_season_stats")
    conn.execute(
        """
        CREATE TABLE nhl_player_season_stats (
            player_id VARCHAR NOT NULL,
            player_name VARCHAR,
            season INTEGER NOT NULL,
            position VARCHAR NOT NULL,
            team VARCHAR,
            games INTEGER,
            goals DOUBLE DEFAULT 0,
            assists DOUBLE DEFAULT 0,
            points DOUBLE DEFAULT 0,
            plus_minus DOUBLE DEFAULT 0,
            shots DOUBLE DEFAULT 0,
            hits DOUBLE DEFAULT 0,
            blocks DOUBLE DEFAULT 0,
            wins DOUBLE DEFAULT 0,
            saves DOUBLE DEFAULT 0,
            goals_against DOUBLE DEFAULT 0,
            shutouts DOUBLE DEFAULT 0,
            fantasy_points_espn DOUBLE,
            PRIMARY KEY (player_id, season, position, team)
        )
        """
    )
    if existing is not None and not existing.empty:
        existing.columns = [str(c).lower() for c in existing.columns]
        if "position" not in existing.columns:
            existing["position"] = "F"
        if "team" not in existing.columns:
            existing["team"] = "UNK"
        from src.sports.nhl.teams import normalize_nhl_team

        existing["team"] = existing["team"].map(normalize_nhl_team)
        conn.register("_nhl_mig", existing)
        cols = ", ".join(NHL_PLAYER_SEASON_COLUMNS)
        conn.execute(
            f"""
            INSERT INTO nhl_player_season_stats ({cols})
            SELECT {cols} FROM _nhl_mig
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY player_id, season, position, team
                ORDER BY games DESC NULLS LAST
            ) = 1
            """
        )
        conn.unregister("_nhl_mig")


def ensure_nhl_player_season_stats_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply NHL DDL and rebuild the stats table if the primary key is outdated."""
    conn.execute(NHL_SEASON_DDL)
    _migrate_nhl_player_season_stats(conn)


def _nhl_game_table_exists(conn: duckdb.DuckDBPyConnection) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE lower(table_name) = 'nhl_player_game_stats'
            LIMIT 1
            """
        ).fetchone()
        return row is not None
    except duckdb.Error:
        return False


def _nhl_game_primary_key_columns(conn: duckdb.DuckDBPyConnection) -> list[str]:
    try:
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.key_column_usage
            WHERE lower(table_name) = 'nhl_player_game_stats'
            ORDER BY ordinal_position
            """
        ).fetchall()
        return [str(r[0]).lower() for r in rows]
    except duckdb.Error:
        return []


def _nhl_game_has_column(conn: duckdb.DuckDBPyConnection, name: str) -> bool:
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE lower(table_name) = 'nhl_player_game_stats'
              AND lower(column_name) = lower(?)
            LIMIT 1
            """,
            [name],
        ).fetchone()
        return row is not None
    except duckdb.Error:
        return False


def _migrate_nhl_player_game_stats(conn: duckdb.DuckDBPyConnection) -> None:
    """Recreate NHL game log table when PK or goalie columns are outdated."""
    if not _nhl_game_table_exists(conn):
        return
    pk = _nhl_game_primary_key_columns(conn)
    needs_rebuild = pk != ["player_id", "season", "game_id", "log_type"] or not _nhl_game_has_column(
        conn, "saves"
    )
    if not needs_rebuild:
        return
    try:
        existing = conn.execute("SELECT * FROM nhl_player_game_stats").df()
    except duckdb.Error:
        existing = None
    conn.execute("DROP TABLE nhl_player_game_stats")
    conn.execute(NHL_GAME_DDL)
    if existing is not None and not existing.empty:
        existing.columns = [str(c).lower() for c in existing.columns]
        if "log_type" not in existing.columns:
            existing["log_type"] = "skater"
        for col in NHL_PLAYER_GAME_COLUMNS:
            if col not in existing.columns:
                existing[col] = None
        conn.register("_nhl_game_mig", existing)
        cols = ", ".join(NHL_PLAYER_GAME_COLUMNS)
        conn.execute(
            f"""
            INSERT INTO nhl_player_game_stats ({cols})
            SELECT {cols} FROM _nhl_game_mig
            """
        )
        conn.unregister("_nhl_game_mig")


def ensure_nhl_player_game_stats_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply NHL game-log DDL and migrate legacy tables."""
    conn.execute(NHL_GAME_DDL)
    _migrate_nhl_player_game_stats(conn)


def init_sport_tables(conn: duckdb.DuckDBPyConnection) -> None:
    ensure_mlb_player_season_stats_schema(conn)
    conn.execute(NBA_SEASON_DDL)
    ensure_nhl_player_season_stats_schema(conn)
    conn.execute(NBA_GAME_DDL)
    ensure_nhl_player_game_stats_schema(conn)
    ensure_mlb_player_game_stats_schema(conn)
