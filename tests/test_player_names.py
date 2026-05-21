"""Player display name resolution."""

import pandas as pd

from src.stats_columns import resolve_player_name


def test_prefers_display_name_over_abbreviated():
    source = pd.DataFrame(
        {
            "player_name": ["A.Abdullah"],
            "player_display_name": ["Ameer Abdullah"],
        }
    )
    assert resolve_player_name(source).iloc[0] == "Ameer Abdullah"


def test_falls_back_to_short_name_when_display_missing():
    source = pd.DataFrame({"player_name": ["A.Abdullah"]})
    assert resolve_player_name(source).iloc[0] == "A.Abdullah"
