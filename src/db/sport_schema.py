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
    PRIMARY KEY (player_id, season, position)
);

CREATE INDEX IF NOT EXISTS idx_mlb_season ON mlb_player_season_stats(season, position);
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
    PRIMARY KEY (player_id, season)
);

CREATE INDEX IF NOT EXISTS idx_nhl_season ON nhl_player_season_stats(season, position);
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


def _migrate_mlb_player_season_stats(conn: duckdb.DuckDBPyConnection) -> None:
    """Recreate MLB table unless PK is (player_id, season, position)."""
    if not _mlb_table_exists(conn):
        return
    names = _mlb_primary_key_columns(conn)
    if names == ["player_id", "season", "position"]:
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
            PRIMARY KEY (player_id, season, position)
        )
        """
    )
    if existing is not None and not existing.empty:
        existing.columns = [str(c).lower() for c in existing.columns]
        if "position" not in existing.columns:
            existing["position"] = "H"
        conn.register("_mlb_mig", existing)
        cols = ", ".join(MLB_PLAYER_SEASON_COLUMNS)
        conn.execute(
            f"""
            INSERT INTO mlb_player_season_stats ({cols})
            SELECT {cols} FROM _mlb_mig
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY player_id, season, position
                ORDER BY games DESC NULLS LAST
            ) = 1
            """
        )
        conn.unregister("_mlb_mig")


def ensure_mlb_player_season_stats_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Apply MLB DDL and rebuild the stats table if the primary key is outdated."""
    conn.execute(MLB_SEASON_DDL)
    _migrate_mlb_player_season_stats(conn)


def init_sport_tables(conn: duckdb.DuckDBPyConnection) -> None:
    ensure_mlb_player_season_stats_schema(conn)
    conn.execute(NBA_SEASON_DDL)
    conn.execute(NHL_SEASON_DDL)
