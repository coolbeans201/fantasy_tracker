"""Resolve sidebar scoring selection to preset keys for queries."""

from __future__ import annotations

import duckdb

from src.scoring.calc import DISPLAY_PRESETS, resolve_preset
from src.scoring.preset_store import (
    CUSTOM_PREFIX,
    list_custom_presets,
    make_custom_preset_key,
)


def builtin_scoring_options() -> list[tuple[str, str]]:
    """(sidebar label, preset_key) for built-in presets."""
    return [(label, key) for label, key in DISPLAY_PRESETS.items()]


def all_scoring_options(conn: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    """Built-in labels plus saved custom presets."""
    options = builtin_scoring_options()
    for row in list_custom_presets(conn):
        options.append((f"★ {row['name']}", row["preset_key"]))
    return options


def resolve_sidebar_selection(selection_label: str, conn: duckdb.DuckDBPyConnection) -> str:
    """
    Map sidebar label to preset_key (half_ppr, standard, or custom:uuid).
    selection_label is the left part of all_scoring_options tuples.
    """
    for label, key in builtin_scoring_options():
        if label == selection_label:
            return key
    for row in list_custom_presets(conn):
        if selection_label == f"★ {row['name']}":
            return row["preset_key"]
    if selection_label.startswith(CUSTOM_PREFIX):
        return selection_label
    return resolve_preset(selection_label)
