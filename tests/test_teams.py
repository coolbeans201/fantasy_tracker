"""NFL team name search for defenses."""

from src.teams import (
    dst_entity_display_name,
    team_codes_matching_query,
    team_full_name,
)


def test_cardinals_resolves_to_ari():
    assert "ARI" in team_codes_matching_query("cardinals")
    assert "ARI" in team_codes_matching_query("Cardinals")


def test_patriots_and_abbreviation():
    assert "NE" in team_codes_matching_query("patriots")
    assert "NE" in team_codes_matching_query("ne")


def test_dst_display_name():
    assert dst_entity_display_name("ARI") == "Arizona Cardinals (ARI)"
    assert team_full_name("ARI") == "Arizona Cardinals"
