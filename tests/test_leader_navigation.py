"""Season Leaders → profile link URLs."""

from app.leader_navigation import leader_profile_url, profile_page_path


def test_sport_profile_paths():
    assert profile_page_path("nfl") == "/nfl_profile"
    assert profile_page_path("mlb") == "/mlb_profile"
    assert profile_page_path("nba") == "/nba_profile"
    assert profile_page_path("nhl") == "/nhl_profile"


def test_leader_profile_url_includes_entity_and_season():
    url = leader_profile_url("592450", 2024, "Mike Trout", sport_id="mlb")
    assert url.startswith("/mlb_profile?")
    assert "entity=592450" in url
    assert "season=2024" in url
    assert "#Mike%20Trout" in url or "#Mike Trout" in url
