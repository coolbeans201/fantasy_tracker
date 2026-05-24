"""Sidebar UI for custom scoring presets."""

from __future__ import annotations

import streamlit as st

from src.scoring.calc import DISPLAY_PRESETS
from src.scoring.offense_weights import offense_weights_from_builtin
from src.scoring.preset_store import (
    delete_custom_preset,
    is_custom_preset_key,
    list_custom_presets,
    save_custom_preset,
    scoring_caption,
)
from src.scoring.selection import all_scoring_options, resolve_sidebar_selection
from src.ui_text import title_case_ui


def _clear_db_cache() -> None:
    """Drop the read-only DuckDB cache so pages see new scoring presets."""
    from app.components import cached_connection

    cached_connection.clear()


def _load_clone_weights(clone_label: str) -> dict[str, float]:
    key = DISPLAY_PRESETS[clone_label]
    return offense_weights_from_builtin(key)


def render_custom_preset_editor(conn, *, active_preset_key: str) -> None:
    """Create or delete custom offense scoring presets."""
    from src.scoring.offense_weights import OFFENSE_SCORING_STATS
    from src.scoring.preset_store import default_weight_form, offense_weight_labels

    if "custom_editor_weights" not in st.session_state:
        st.session_state.custom_editor_weights = default_weight_form()

    clone_label = st.selectbox(
        title_case_ui("Clone from"),
        list(DISPLAY_PRESETS.keys()),
        index=1,
        key="custom_scoring_clone",
    )
    if st.button(title_case_ui("Load clone weights"), key="custom_scoring_load_clone"):
        st.session_state.custom_editor_weights = _load_clone_weights(clone_label)

    if is_custom_preset_key(active_preset_key):
        active = next(
            (p for p in list_custom_presets(conn) if p["preset_key"] == active_preset_key),
            None,
        )
        if active and st.button(title_case_ui("Load active preset into editor"), key="custom_load_active"):
            st.session_state.custom_editor_weights = dict(active["offense_weights"])

    weights: dict[str, float] = {}
    for stat, label in offense_weight_labels():
        default = float(st.session_state.custom_editor_weights.get(stat, 0.0))
        weights[stat] = st.number_input(
            label,
            value=default,
            step=0.25,
            format="%.2f",
            key=f"custom_scoring_wt_{stat}",
        )

    preset_name = st.text_input(
        title_case_ui("Preset name"),
        placeholder="My league scoring",
        key="custom_scoring_name",
    )

    if st.button(title_case_ui("Save preset"), key="custom_scoring_save"):
        try:
            save_custom_preset(conn, preset_name, weights)
            st.success(f"Saved **{preset_name.strip()}**. Select it from the Scoring list (★).")
            st.session_state.custom_editor_weights = weights
            _clear_db_cache()
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    customs = list_custom_presets(conn)
    if customs:
        st.divider()
        del_name = st.selectbox(
            title_case_ui("Delete preset"),
            [c["name"] for c in customs],
            key="custom_scoring_delete_pick",
        )
        if st.button(title_case_ui("Delete selected"), key="custom_scoring_delete"):
            target = next(c for c in customs if c["name"] == del_name)
            delete_custom_preset(conn, target["preset_key"])
            st.success(f"Deleted **{del_name}**.")
            _clear_db_cache()
            st.rerun()


def render_scoring_sidebar(conn) -> tuple[str, str]:
    """
    Scoring selectbox + custom preset editor.
    Returns (selection_label, preset_key).
    """
    options = all_scoring_options(conn)
    labels = [label for label, _ in options]
    default_label = st.session_state.get("scoring_selection_label", "Half-PPR")
    if default_label not in labels:
        default_label = "Half-PPR" if "Half-PPR" in labels else labels[0]
    index = labels.index(default_label)

    chosen_label = st.sidebar.selectbox(
        title_case_ui("Scoring"),
        labels,
        index=index,
        key="sidebar_scoring_select",
    )
    st.session_state.scoring_selection_label = chosen_label
    preset_key = resolve_sidebar_selection(chosen_label, conn)
    st.sidebar.caption(scoring_caption(conn, preset_key))

    with st.sidebar.expander(title_case_ui("Custom scoring presets"), expanded=False):
        render_custom_preset_editor(conn, active_preset_key=preset_key)

    return chosen_label, preset_key
