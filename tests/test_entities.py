"""Fantasy entity id helpers (players + dst:TEAM)."""

from src.entities import (
    dst_display_name,
    dst_team_from_entity,
    is_dst_entity,
    make_dst_entity_id,
)


def test_dst_entity_roundtrip():
    assert make_dst_entity_id("den") == "dst:DEN"
    assert is_dst_entity("dst:DEN")
    assert not is_dst_entity("00-0031234")
    assert dst_team_from_entity("dst:DEN") == "DEN"
    assert dst_display_name("DEN") == "DEN Defense"
