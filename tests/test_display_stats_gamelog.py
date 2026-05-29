from src.sports.display_stats import game_log_stat_columns


def test_game_log_stat_columns_mlb_pitching_by_log_type():
    cols = game_log_stat_columns("mlb", "DH", log_type="pitching")
    assert cols == ["wins", "strikeouts_pitch", "saves", "innings_pitched"]


def test_game_log_stat_columns_mlb_hitting_by_log_type():
    cols = game_log_stat_columns("mlb", "SP", log_type="hitting")
    assert "runs" in cols
    assert "wins" not in cols
