"""NHL fantasy positions (skaters vs goalies)."""

from __future__ import annotations

SKATER_POSITION = "S"
GOALIE_POSITION = "G"
LEADER_POSITIONS = [SKATER_POSITION, GOALIE_POSITION]


def leader_position_options() -> list[str]:
    return list(LEADER_POSITIONS)


def coerce_leader_selection(selected: list[str] | None, previous: list[str] | None = None) -> list[str]:
    del previous
    sel = list(selected or [])
    if sel == [GOALIE_POSITION]:
        return [GOALIE_POSITION]
    return [SKATER_POSITION]
