"""Custom offense scoring presets and query-time FP."""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from src.db.connection import init_schema
from src.scoring.calc import compute_fantasy_points, fantasy_points_sql_expr, load_presets
from src.scoring.offense_weights import (
    compute_offense_fp_series,
    offense_fp_sql_sum,
    offense_weights_from_builtin,
    validate_offense_weights,
)
from src.scoring.preset_store import (
    get_offense_weights,
    is_custom_preset_key,
    list_custom_presets,
    save_custom_preset,
    scoring_caption,
)


@pytest.fixture
def mem_conn():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    return conn


def test_validate_offense_weights_rejects_unknown_stat():
    with pytest.raises(ValueError, match="Unknown scoring stat"):
        validate_offense_weights({"bogus": 1.0})


def test_builtin_weights_match_yaml():
    for key in ("standard", "half_ppr", "full_ppr"):
        weights = offense_weights_from_builtin(key)
        yaml_weights = load_presets()[key]
        for stat in weights:
            assert weights[stat] == pytest.approx(float(yaml_weights[stat]))


def test_compute_offense_fp_matches_builtin_column():
    row = pd.DataFrame(
        [
            {
                "passing_yards": 300,
                "passing_tds": 2,
                "interceptions": 1,
                "rushing_yards": 20,
                "rushing_tds": 0,
                "receptions": 5,
                "receiving_yards": 60,
                "receiving_tds": 1,
                "fumbles_lost": 0,
            }
        ]
    )
    for key in ("standard", "half_ppr", "full_ppr"):
        weights = offense_weights_from_builtin(key)
        expected = float(compute_fantasy_points(row, key).iloc[0])
        actual = float(compute_offense_fp_series(row, weights).iloc[0])
        assert actual == pytest.approx(expected)


def test_offense_fp_sql_sum_roundtrip(mem_conn):
    weights = offense_weights_from_builtin("half_ppr")
    expr = offense_fp_sql_sum(weights)
    row = mem_conn.execute(
        f"""
        SELECT {expr} AS fp FROM (
            SELECT
                300.0 AS passing_yards, 2 AS passing_tds, 1 AS interceptions,
                20.0 AS rushing_yards, 0 AS rushing_tds,
                5 AS receptions, 60.0 AS receiving_yards, 1 AS receiving_tds,
                0 AS fumbles_lost
        ) t
        """
    ).fetchone()
    assert row[0] is not None


def test_custom_preset_roundtrip(mem_conn):
    weights = offense_weights_from_builtin("full_ppr")
    weights["receptions"] = 1.25
    key = save_custom_preset(mem_conn, "Test League", weights)
    assert is_custom_preset_key(key)
    customs = list_custom_presets(mem_conn)
    assert len(customs) == 1
    assert customs[0]["name"] == "Test League"
    loaded = get_offense_weights(mem_conn, key)
    assert loaded["receptions"] == pytest.approx(1.25)


def test_fantasy_points_sql_expr_custom(mem_conn):
    key = save_custom_preset(mem_conn, "Custom", {"receptions": 2.0, "receiving_yards": 0.1})
    expr = fantasy_points_sql_expr(key, mem_conn)
    assert "receptions" in expr
    assert "fantasy_points_half_ppr" not in expr


def test_fantasy_points_sql_expr_builtin_uses_column():
    expr = fantasy_points_sql_expr("half_ppr", None)
    assert "fantasy_points_half_ppr" in expr


def test_scoring_caption_mentions_custom(mem_conn):
    key = save_custom_preset(mem_conn, "My League", offense_weights_from_builtin("standard"))
    cap = scoring_caption(mem_conn, key)
    assert "My League" in cap
    assert "ESPN" in cap
