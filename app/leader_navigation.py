"""Clickable player/team names in Season Leaders → Player Profile."""

from __future__ import annotations

from urllib.parse import quote, urlencode

import pandas as pd
import streamlit as st

# Multipage slug for app/pages/2_Player_Profile.py (numeric prefix stripped).
PROFILE_PAGE_URL = "/Player_Profile"

_NAME_LINK_DISPLAY = r".*#(.+)$"


def leader_profile_url(entity_id: str, season: int, display_name: str) -> str:
    """Build a same-app profile URL; fragment supplies LinkColumn display text."""
    query = urlencode({"entity": entity_id, "season": str(season)})
    fragment = quote(str(display_name), safe=" ")
    return f"{PROFILE_PAGE_URL}?{query}#{fragment}"


def inject_name_profile_links(
    display_df: pd.DataFrame,
    *,
    entity_ids: pd.Series,
    display_names: pd.Series,
    season: int,
    name_column: str,
) -> pd.DataFrame:
    out = display_df.copy()
    out[name_column] = [
        leader_profile_url(str(eid), int(season), str(name))
        for eid, name in zip(entity_ids, display_names, strict=True)
    ]
    return out


def profile_name_link_column_config(name_column: str) -> dict:
    return {
        name_column: st.column_config.LinkColumn(
            name_column,
            display_text=_NAME_LINK_DISPLAY,
            help="Open in Player Profile",
        ),
    }


def render_leaders_table(
    display_df: pd.DataFrame,
    *,
    entity_ids: pd.Series,
    display_names: pd.Series,
    season: int,
    name_column: str,
) -> None:
    linked = inject_name_profile_links(
        display_df,
        entity_ids=entity_ids,
        display_names=display_names,
        season=season,
        name_column=name_column,
    )
    st.caption(f"Click a **{name_column}** name to open **Player Profile**.")
    st.dataframe(
        linked,
        use_container_width=True,
        hide_index=True,
        column_config=profile_name_link_column_config(name_column),
    )
