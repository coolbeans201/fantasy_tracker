import duckdb

from src.sports.player_search import search_players_table
from src.text_encoding import fold_for_search, player_name_matches_query


def test_fold_for_search_strips_accents():
    assert fold_for_search("Nikola Jokić") == "nikola jokic"


def test_player_name_matches_query_accent_insensitive():
    assert player_name_matches_query("Nikola Jokić", "Nikola Jokic")
    assert player_name_matches_query("Nikola Jokić", "jokic")
    assert not player_name_matches_query("Nikola Jokić", "curry")


def test_search_players_table_last_name_without_accent():
    conn = duckdb.connect()
    conn.execute(
        """
        CREATE TABLE nba_player_season_stats (
            player_id VARCHAR,
            player_name VARCHAR,
            position VARCHAR,
            season INTEGER
        )
        """
    )
    conn.execute(
        """
        INSERT INTO nba_player_season_stats VALUES
            ('jokic', 'Nikola Jokić', 'C', 2026),
            ('curry', 'Stephen Curry', 'G', 2026)
        """
    )
    hits = search_players_table(conn, "nba_player_season_stats", "jokic", limit=10)
    assert len(hits) == 1
    assert hits.iloc[0]["player_id"] == "jokic"
