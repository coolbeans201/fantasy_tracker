from app.leader_navigation import leader_profile_url


def test_leader_profile_url_encodes_entity_and_shows_name():
    url = leader_profile_url("dst:DEN", 2023, "DEN")
    assert url.startswith("/Player_Profile?")
    assert "entity=dst%3ADEN" in url
    assert "season=2023" in url
    assert url.endswith("#DEN")


def test_leader_profile_url_preserves_spaces_in_display_name():
    url = leader_profile_url("00-0033873", 2022, "Patrick Mahomes")
    assert "#Patrick Mahomes" in url
