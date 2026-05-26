"""DuckDB connection helpers."""



from __future__ import annotations



from pathlib import Path



import duckdb



from src.db.maintenance import (
    players_table_needs_rebuild,
    recompute_games_played,
    rebuild_players_table,
    refresh_player_display_names,
)



ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"

DB_PATH = DATA_DIR / "fantasy_tracker.duckdb"

SCHEMA_PATH = Path(__file__).parent / "schema.sql"



__all__ = [

    "DATA_DIR",

    "DB_PATH",

    "db_exists",

    "get_connection",

    "init_schema",

    "list_ingested_seasons",

    "players_table_needs_rebuild",

    "recompute_games_played",

    "rebuild_players_table",

    "refresh_player_display_names",

]





def ensure_data_dir() -> Path:

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    return DATA_DIR





def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:

    ensure_data_dir()

    return duckdb.connect(str(DB_PATH), read_only=read_only)





def _migrate_stat_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add stat columns to existing databases created before schema expansion."""
    from src.kicker_columns import KICKER_STAT_COLUMNS
    from src.stats_columns import STAT_COLUMNS

    player_tables = ("weekly_stats", "season_team_stats", "season_stats")
    for table in player_tables:
        for col in STAT_COLUMNS + KICKER_STAT_COLUMNS:
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} DOUBLE DEFAULT 0"
                )
            except duckdb.Error:
                pass
        for col in ("fantasy_points_kicker",):
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} DOUBLE"
                )
            except duckdb.Error:
                pass
    try:
        conn.execute(
            "ALTER TABLE season_stats ADD COLUMN IF NOT EXISTS best_week_scoring VARCHAR"
        )
    except duckdb.Error:
        pass
    for table in ("weekly_stats", "team_defense_weekly"):
        try:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS opponent VARCHAR"
            )
        except duckdb.Error:
            pass
    for table in ("team_defense_weekly", "team_defense_season"):
        try:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS yards_allowed DOUBLE DEFAULT 0"
            )
        except duckdb.Error:
            pass
    _migrate_rankings_tables(conn)
    _migrate_scoring_presets_table(conn)
    _migrate_sport_columns(conn)
    from src.db.sport_schema import init_sport_tables

    init_sport_tables(conn)


def _migrate_sport_columns(conn: duckdb.DuckDBPyConnection) -> None:
    """Add sport to ingest_manifest and players for multi-sport metadata."""
    try:
        cols = {
            str(r[0]).lower()
            for r in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'ingest_manifest'"
            ).fetchall()
        }
    except duckdb.Error:
        cols = set()

    if cols and "sport" not in cols:
        conn.execute(
            """
            CREATE TABLE ingest_manifest_new (
                sport VARCHAR NOT NULL DEFAULT 'nfl',
                season INTEGER NOT NULL,
                ingested_at TIMESTAMP NOT NULL,
                row_count INTEGER,
                PRIMARY KEY (sport, season)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ingest_manifest_new (sport, season, ingested_at, row_count)
            SELECT 'nfl', season, ingested_at, row_count FROM ingest_manifest
            """
        )
        conn.execute("DROP TABLE ingest_manifest")
        conn.execute("ALTER TABLE ingest_manifest_new RENAME TO ingest_manifest")

    try:
        pcols = {
            str(r[0]).lower()
            for r in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'players'"
            ).fetchall()
        }
    except duckdb.Error:
        pcols = set()

    if pcols and "sport" not in pcols:
        conn.execute(
            """
            CREATE TABLE players_new (
                sport VARCHAR NOT NULL DEFAULT 'nfl',
                player_id VARCHAR NOT NULL,
                player_name VARCHAR NOT NULL,
                position VARCHAR,
                last_season INTEGER,
                PRIMARY KEY (sport, player_id)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO players_new (sport, player_id, player_name, position, last_season)
            SELECT 'nfl', player_id, player_name, position, last_season FROM players
            """
        )
        conn.execute("DROP TABLE players")
        conn.execute("ALTER TABLE players_new RENAME TO players")


def _migrate_scoring_presets_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scoring_presets (
            preset_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            sport VARCHAR NOT NULL DEFAULT 'nfl',
            offense_weights VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
        """
    )
    try:
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_scoring_presets_name
            ON scoring_presets(sport, name)
            """
        )
    except duckdb.Error:
        pass


def _migrate_rankings_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Create FantasyPros ECR tables on existing databases."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ecr_draft (
            player_id VARCHAR NOT NULL,
            season INTEGER NOT NULL,
            position VARCHAR NOT NULL,
            ecr_rank INTEGER NOT NULL,
            ecr_sd DOUBLE,
            player_name VARCHAR,
            team VARCHAR,
            fantasypros_id VARCHAR,
            scrape_date DATE,
            PRIMARY KEY (player_id, season, position)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ecr_weekly (
            player_id VARCHAR NOT NULL,
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            position VARCHAR NOT NULL,
            ecr_rank INTEGER NOT NULL,
            ecr_sd DOUBLE,
            player_name VARCHAR,
            team VARCHAR,
            fantasypros_id VARCHAR,
            scrape_date DATE,
            PRIMARY KEY (player_id, season, week, position)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rankings_manifest (
            ingested_at TIMESTAMP NOT NULL,
            draft_rows INTEGER,
            weekly_rows INTEGER,
            seasons_min INTEGER,
            seasons_max INTEGER
        )
        """
    )
    try:
        conn.execute("ALTER TABLE ecr_draft ADD COLUMN sport VARCHAR DEFAULT 'nfl'")
    except duckdb.Error:
        pass
    try:
        conn.execute("ALTER TABLE ecr_weekly ADD COLUMN sport VARCHAR DEFAULT 'nfl'")
    except duckdb.Error:
        pass





def init_schema(conn: duckdb.DuckDBPyConnection | None = None) -> None:

    close = False

    if conn is None:

        conn = get_connection()

        close = True

    sql = SCHEMA_PATH.read_text(encoding="utf-8")

    conn.execute(sql)

    _migrate_stat_columns(conn)

    if close:

        conn.close()





def db_exists() -> bool:

    return DB_PATH.exists()





def list_ingested_seasons(
    conn: duckdb.DuckDBPyConnection | None = None,
    *,
    sport: str = "nfl",
) -> list[int]:

    close = False

    if conn is None:

        if not db_exists():

            return []

        conn = get_connection()

        close = True

    rows = conn.execute(
        """
        SELECT season FROM ingest_manifest
        WHERE sport = ?
        ORDER BY season DESC
        """,
        [sport],
    ).fetchall()

    if close:

        conn.close()

    return [int(r[0]) for r in rows]


def list_sport_seasons(
    conn: duckdb.DuckDBPyConnection,
    sport: str,
) -> list[int]:
    """Ingested seasons for a sport (NFL uses ingest_manifest; others use sport manifest)."""
    sport = str(sport).strip().lower()
    if sport == "nfl":
        return list_ingested_seasons(conn, sport="nfl")
    table_map = {
        "mlb": "mlb_ingest_manifest",
        "nba": "nba_ingest_manifest",
        "nhl": "nhl_ingest_manifest",
    }
    table = table_map.get(sport)
    if not table:
        return []
    try:
        rows = conn.execute(
            f"SELECT season FROM {table} ORDER BY season DESC"
        ).fetchall()
    except duckdb.Error:
        return []
    return [int(r[0]) for r in rows]


def get_ingest_summary(conn: duckdb.DuckDBPyConnection | None = None) -> dict:
    """Seasons ingested, row counts, and latest ingest timestamp."""
    empty = {
        "seasons": [],
        "season_count": 0,
        "latest_season": None,
        "latest_ingested_at": None,
        "total_rows": 0,
    }
    if not db_exists():
        return empty

    close = False
    if conn is None:
        conn = get_connection()
        close = True

    try:
        manifest = conn.execute(
            """
            SELECT season, ingested_at, row_count
            FROM ingest_manifest
            WHERE sport = 'nfl'
            ORDER BY season DESC
            """
        ).df()
    except duckdb.Error:
        manifest = None

    if close:
        conn.close()

    if manifest is None or manifest.empty:
        seasons = list_ingested_seasons()
        return {
            **empty,
            "seasons": seasons,
            "season_count": len(seasons),
            "latest_season": seasons[0] if seasons else None,
        }

    manifest.columns = [str(c).lower() for c in manifest.columns]
    seasons = [int(s) for s in manifest["season"].tolist()]
    return {
        "seasons": seasons,
        "season_count": len(seasons),
        "latest_season": seasons[0] if seasons else None,
        "latest_ingested_at": manifest["ingested_at"].max(),
        "total_rows": int(manifest["row_count"].fillna(0).sum()),
    }


