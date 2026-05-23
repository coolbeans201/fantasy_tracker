"""Display labels and combined fumble stats."""

from src.stats_columns import (
    build_stat_compare_frame,
    column_display_label,
    combined_fumbles_lost,
    display_stats_for_positions,
    rename_stats_for_display,
    stat_display_label,
    stat_display_value,
)
import pandas as pd


def test_column_display_label_for_metadata_columns():
    assert column_display_label("fantasy_points") == "Fantasy Points"
    assert column_display_label("player_name") == "Player"
    assert column_display_label("peer_z_season") == "Peer Z (Season)"
    assert column_display_label("rank_delta") == "Rank Δ"


def test_rename_stats_for_display_all_columns():
    df = pd.DataFrame(
        {
            "player_name": ["Ameer Abdullah"],
            "fantasy_points": [100.0],
            "rushing_yards": [500.0],
        }
    )
    out = rename_stats_for_display(df)
    assert list(out.columns) == ["Player", "Fantasy Points", "Rushing Yards"]


def test_stat_display_label_readable():
    assert stat_display_label("rushing_yards") == "Rushing Yards"
    assert stat_display_label("sacks_suffered") == "Sacks"
    assert stat_display_label("fumbles_lost") == "Fumbles Lost"


def test_display_stats_collapses_fumble_columns():
    cols = display_stats_for_positions(["RB"])
    assert "rushing_fumbles_lost" not in cols
    assert "receiving_fumbles_lost" not in cols
    assert "fumbles_lost" in cols


def test_combined_fumbles_prefers_total_column():
    row = {"fumbles_lost": 3, "rushing_fumbles_lost": 1, "receiving_fumbles_lost": 2}
    assert combined_fumbles_lost(row) == 3


def test_combined_fumbles_sums_components_when_total_missing():
    row = {"fumbles_lost": 0, "rushing_fumbles_lost": 1, "receiving_fumbles_lost": 2}
    assert combined_fumbles_lost(row) == 3


def test_build_stat_compare_frame_uses_labels():
    from src.stats_columns import rename_stats_for_display

    row_a = {"rushing_yards": 1000, "rushing_fumbles_lost": 1, "receiving_fumbles_lost": 0}
    row_b = {"rushing_yards": 800, "fumbles_lost": 2}
    df = rename_stats_for_display(build_stat_compare_frame(row_a, row_b, "Alice", "Bob", ["RB"]))
    assert "Stat" in df.columns
    assert "Rushing Yards" in df["Stat"].values
    assert "Fumbles Lost" in df["Stat"].values
    fum = df.loc[df["Stat"] == "Fumbles Lost"].iloc[0]
    assert fum["Alice"] == 1
    assert fum["Bob"] == 2
