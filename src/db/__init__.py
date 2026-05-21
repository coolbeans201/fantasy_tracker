"""Database package."""

from src.db.connection import (
    DATA_DIR,
    DB_PATH,
    db_exists,
    get_connection,
    init_schema,
    list_ingested_seasons,
)
from src.db.maintenance import (
    players_table_needs_rebuild,
    recompute_games_played,
    rebuild_players_table,
    refresh_player_display_names,
)

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
