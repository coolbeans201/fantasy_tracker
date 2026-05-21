"""Fantasy entity IDs: players (player_id) and team defenses (dst:TEAM)."""

from __future__ import annotations

DST_ENTITY_PREFIX = "dst:"


def is_dst_entity(entity_id: str | None) -> bool:
    return str(entity_id or "").startswith(DST_ENTITY_PREFIX)


def make_dst_entity_id(team: str) -> str:
    return f"{DST_ENTITY_PREFIX}{str(team).strip().upper()}"


def dst_team_from_entity(entity_id: str) -> str:
    if not is_dst_entity(entity_id):
        raise ValueError(f"Not a team defense entity id: {entity_id}")
    return entity_id[len(DST_ENTITY_PREFIX) :]


def dst_display_name(team: str) -> str:
    from src.teams import dst_entity_display_name

    return dst_entity_display_name(team)
