"""Sidebar season lists scoped to a player (profile) or compare pair."""

from __future__ import annotations

import streamlit as st


def _profile_seasons_key(sport_id: str) -> str:
    return f"profile_entity_seasons_{sport_id}"


def _profile_entity_key(sport_id: str) -> str:
    return f"profile_seasons_entity_{sport_id}"


def _profile_default_key(sport_id: str) -> str:
    return f"profile_season_default_{sport_id}"


def _compare_seasons_key(sport_id: str) -> str:
    return f"compare_sidebar_seasons_{sport_id}"


def _compare_pair_key(sport_id: str) -> str:
    return f"compare_seasons_pair_{sport_id}"


def _compare_default_key(sport_id: str) -> str:
    return f"compare_season_default_{sport_id}"


def profile_season_scope_caption(seasons: list[int] | None) -> str | None:
    if not seasons:
        return None
    if len(seasons) == 1:
        return f"Season list: this player's **{seasons[0]}** season only."
    return (
        f"Season list: this player's career (**{seasons[-1]}–{seasons[0]}**, "
        f"{len(seasons)} seasons)."
    )


def compare_season_scope_caption(
    union_seasons: list[int] | None,
    *,
    shared_seasons: list[int] | None = None,
) -> str | None:
    if not union_seasons:
        return None
    if len(union_seasons) == 1:
        base = f"Season list: **{union_seasons[0]}** — a year at least one selection has data."
    else:
        base = (
            f"Season list: any year either selection has data "
            f"(**{union_seasons[-1]}–{union_seasons[0]}**, {len(union_seasons)} seasons)."
        )
    if shared_seasons:
        if len(shared_seasons) == 1:
            base += f" Both played in **{shared_seasons[0]}**."
        else:
            base += (
                f" Seasons both played: **{shared_seasons[-1]}–{shared_seasons[0]}** "
                f"({len(shared_seasons)} years)."
            )
    return base


def sync_profile_sidebar_seasons(
    sport_id: str,
    player_id: str,
    available: list[int],
    query_season: int | None,
) -> None:
    """Limit sidebar seasons to the selected player; rerun when player changes."""
    prev_entity = st.session_state.get(_profile_entity_key(sport_id))
    st.session_state[_profile_seasons_key(sport_id)] = available

    if not available:
        return

    if player_id != prev_entity:
        st.session_state[_profile_entity_key(sport_id)] = player_id
        if query_season is not None and int(query_season) in available:
            st.session_state[_profile_default_key(sport_id)] = int(query_season)
        else:
            st.session_state[_profile_default_key(sport_id)] = max(available)
        st.rerun()

    current = st.session_state.get(_profile_default_key(sport_id))
    if current not in available:
        st.session_state[_profile_default_key(sport_id)] = (
            int(query_season)
            if query_season is not None and int(query_season) in available
            else max(available)
        )
        st.rerun()


def sync_compare_sidebar_seasons(
    sport_id: str,
    player_id_a: str,
    player_id_b: str,
    union_seasons: list[int],
    *,
    shared_seasons: list[int] | None = None,
) -> None:
    """Limit sidebar seasons to the compare pair (union of both careers)."""
    pair_key = f"{player_id_a}|{player_id_b}"
    st.session_state[_compare_seasons_key(sport_id)] = union_seasons
    if shared_seasons is not None:
        st.session_state[f"compare_shared_seasons_{sport_id}"] = shared_seasons

    if not union_seasons:
        return

    if pair_key != st.session_state.get(_compare_pair_key(sport_id)):
        st.session_state[_compare_pair_key(sport_id)] = pair_key
        st.session_state[_compare_default_key(sport_id)] = max(union_seasons)
        st.rerun()

    current = st.session_state.get(_compare_default_key(sport_id))
    if current not in union_seasons:
        st.session_state[_compare_default_key(sport_id)] = max(union_seasons)
        st.rerun()


def seasons_for_profile_sidebar(sport_id: str) -> list[int] | None:
    return st.session_state.get(_profile_seasons_key(sport_id))


def seasons_for_compare_sidebar(sport_id: str) -> list[int] | None:
    return st.session_state.get(_compare_seasons_key(sport_id))
