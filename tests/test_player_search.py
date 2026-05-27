from src.text_encoding import fold_for_search, player_name_matches_query


def test_fold_for_search_strips_accents():
    assert fold_for_search("Nikola Jokić") == "nikola jokic"


def test_player_name_matches_query_accent_insensitive():
    assert player_name_matches_query("Nikola Jokić", "Nikola Jokic")
    assert player_name_matches_query("Nikola Jokić", "jokic")
    assert not player_name_matches_query("Nikola Jokić", "curry")
