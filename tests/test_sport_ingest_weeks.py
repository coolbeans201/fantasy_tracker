from src.rankings.sport_ingest import _parse_week_range, max_fp_weeks


def test_parse_week_range_span():
    weeks = _parse_week_range("1-3", sport_id="nba")
    assert weeks == [1, 2, 3]


def test_parse_week_range_caps_at_sport_max():
    cap = max_fp_weeks("nba")
    weeks = _parse_week_range(f"1-{cap + 5}", sport_id="nba")
    assert weeks[-1] == cap
    assert cap + 5 not in weeks
