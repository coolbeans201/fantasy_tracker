"""Persist and load user-defined custom scoring presets."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import duckdb

from src.scoring.offense_weights import (
    OFFENSE_SCORING_STATS,
    offense_weights_from_builtin,
    validate_offense_weights,
)

CUSTOM_PREFIX = "custom:"
DEFAULT_SPORT = "nfl"


def is_custom_preset_key(preset_key: str) -> bool:
    return str(preset_key or "").startswith(CUSTOM_PREFIX)


def custom_preset_id(preset_key: str) -> str:
    if not is_custom_preset_key(preset_key):
        raise ValueError(f"Not a custom preset key: {preset_key}")
    return preset_key.split(":", 1)[1]


def make_custom_preset_key(preset_id: str) -> str:
    return f"{CUSTOM_PREFIX}{preset_id}"


def _ensure_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scoring_presets (
            preset_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            sport VARCHAR NOT NULL DEFAULT 'nfl',
            offense_weights VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
        """
    )


def list_custom_presets(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    _ensure_table(conn)
    try:
        df = conn.execute(
            """
            SELECT preset_id, name, sport, offense_weights, created_at
            FROM scoring_presets
            WHERE sport = ?
            ORDER BY name
            """,
            [DEFAULT_SPORT],
        ).df()
    except duckdb.Error:
        return []
    if df.empty:
        return []
    df.columns = [str(c).lower() for c in df.columns]
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "preset_id": str(row["preset_id"]),
                "preset_key": make_custom_preset_key(str(row["preset_id"])),
                "name": str(row["name"]),
                "sport": str(row["sport"]),
                "offense_weights": json.loads(row["offense_weights"]),
                "created_at": row["created_at"],
            }
        )
    return rows


def get_custom_preset(
    conn: duckdb.DuckDBPyConnection,
    preset_key: str,
) -> dict[str, Any] | None:
    if not is_custom_preset_key(preset_key):
        return None
    pid = custom_preset_id(preset_key)
    _ensure_table(conn)
    row = conn.execute(
        """
        SELECT preset_id, name, sport, offense_weights, created_at
        FROM scoring_presets
        WHERE preset_id = ?
        """,
        [pid],
    ).fetchone()
    if not row:
        return None
    return {
        "preset_id": str(row[0]),
        "preset_key": make_custom_preset_key(str(row[0])),
        "name": str(row[1]),
        "sport": str(row[2]),
        "offense_weights": json.loads(str(row[3])),
        "created_at": row[4],
    }


def get_offense_weights(conn: duckdb.DuckDBPyConnection, preset_key: str) -> dict[str, float]:
    if is_custom_preset_key(preset_key):
        rec = get_custom_preset(conn, preset_key)
        if rec is None:
            raise ValueError(f"Custom preset not found: {preset_key}")
        return validate_offense_weights(rec["offense_weights"])
    from src.scoring.calc import SCORING_PRESETS, resolve_preset

    key = resolve_preset(preset_key) if preset_key not in SCORING_PRESETS else preset_key
    if key in SCORING_PRESETS:
        return offense_weights_from_builtin(key)
    return offense_weights_from_builtin(resolve_preset(preset_key))


def save_custom_preset(
    conn: duckdb.DuckDBPyConnection,
    name: str,
    offense_weights: dict[str, float],
    *,
    preset_id: str | None = None,
) -> str:
    """Insert or update custom preset; returns preset_key."""
    _ensure_table(conn)
    clean_name = str(name).strip()
    if not clean_name:
        raise ValueError("Preset name is required.")
    weights = validate_offense_weights(offense_weights)
    pid = preset_id or str(uuid.uuid4())
    payload = json.dumps(weights)
    now = datetime.now(timezone.utc)

    existing = conn.execute(
        "SELECT preset_id FROM scoring_presets WHERE name = ? AND sport = ?",
        [clean_name, DEFAULT_SPORT],
    ).fetchone()
    if existing and str(existing[0]) != pid:
        raise ValueError(f"A preset named '{clean_name}' already exists.")

    conn.execute("DELETE FROM scoring_presets WHERE preset_id = ?", [pid])
    conn.execute(
        """
        INSERT INTO scoring_presets (preset_id, name, sport, offense_weights, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [pid, clean_name, DEFAULT_SPORT, payload, now],
    )
    return make_custom_preset_key(pid)


def delete_custom_preset(conn: duckdb.DuckDBPyConnection, preset_key: str) -> bool:
    if not is_custom_preset_key(preset_key):
        return False
    _ensure_table(conn)
    pid = custom_preset_id(preset_key)
    conn.execute("DELETE FROM scoring_presets WHERE preset_id = ?", [pid])
    return True


def preset_label(conn: duckdb.DuckDBPyConnection, preset_key: str) -> str:
    if is_custom_preset_key(preset_key):
        rec = get_custom_preset(conn, preset_key)
        return rec["name"] if rec else preset_key
    from src.scoring.calc import DISPLAY_PRESETS, resolve_preset

    key = preset_key
    if preset_key in DISPLAY_PRESETS:
        return preset_key
    try:
        key = resolve_preset(preset_key)
    except ValueError:
        return preset_key
    for label, k in DISPLAY_PRESETS.items():
        if k == key:
            return label
    return preset_key


def scoring_caption(conn: duckdb.DuckDBPyConnection, preset_key: str) -> str:
    """Short UI note for K/DST when offense uses built-in or custom rules."""
    label = preset_label(conn, preset_key)
    if is_custom_preset_key(preset_key):
        return (
            f"Offense (QB/RB/WR/TE) uses custom preset **{label}**. "
            "Kickers and D/ST use ESPN default scoring."
        )
    return (
        f"Offense uses **{label}** scoring. Kickers and D/ST use ESPN default."
    )


def default_weight_form() -> dict[str, float]:
    """Starter form values from Half-PPR built-in."""
    return offense_weights_from_builtin("half_ppr")


def offense_weight_labels() -> list[tuple[str, str]]:
    """(stat_key, display label) for editor."""
    from src.stats_columns import column_display_label

    return [(s, column_display_label(s)) for s in OFFENSE_SCORING_STATS]
