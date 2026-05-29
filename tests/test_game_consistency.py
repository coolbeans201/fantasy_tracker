"""Player-relative game log boom/bust helpers."""

from __future__ import annotations

import pandas as pd

from src.analytics.game_consistency import (
    game_boom_bust_tags,
    player_game_fp_percentiles,
)
from src.sports.game_logs import filter_game_log_for_profile


def test_player_game_fp_percentiles():
    games = pd.DataFrame({"fantasy_points": [1.0, 2.0, 3.0, 4.0, 5.0]})
    p25, p75 = player_game_fp_percentiles(games)
    assert p25 == 2.0
    assert p75 == 4.0


def test_game_boom_bust_tags():
    games = pd.DataFrame({"fantasy_points": [1.0, 3.0, 5.0]})
    tags = game_boom_bust_tags(games, p25=2.0, p75=4.0)
    assert tags.tolist() == ["Weak", "", "Strong"]


def test_filter_mlb_game_log_legacy_without_stat_columns():
    games = pd.DataFrame(
        [{"game_id": "1", "fantasy_points": 8.0}, {"game_id": "2", "fantasy_points": 3.0}]
    )
    out = filter_game_log_for_profile(games, "mlb", "OF")
    assert len(out) == 2


def test_filter_mlb_game_log_explicit_log_type():
    games = pd.DataFrame(
        [
            {"game_id": "1", "log_type": "hitting", "runs": 1, "fantasy_points": 5.0},
            {"game_id": "1", "log_type": "pitching", "innings_pitched": 6, "fantasy_points": 20.0},
        ]
    )
    pit = filter_game_log_for_profile(games, "mlb", "DH", log_type="pitching")
    assert len(pit) == 1
    assert pit.iloc[0]["log_type"] == "pitching"


def test_enrich_mlb_game_log_rows_splits_pitching():
    games = pd.DataFrame(
        [
            {
                "game_id": "1",
                "log_type": "hitting",
                "runs": 1,
                "innings_pitched": 0,
                "fantasy_points": 5.0,
            },
            {
                "game_id": "2",
                "log_type": "hitting",
                "runs": None,
                "innings_pitched": 6,
                "fantasy_points": 20.0,
            },
        ]
    )
    from src.sports.game_logs import enrich_mlb_game_log_rows, mlb_game_log_types_present

    enriched = enrich_mlb_game_log_rows(games)
    assert mlb_game_log_types_present(enriched) == {"hitting", "pitching"}
    assert enriched.iloc[1]["log_type"] == "pitching"


def test_mlb_game_log_types_present():
    games = pd.DataFrame(
        [
            {"log_type": "hitting"},
            {"log_type": "pitching"},
        ]
    )
    from src.sports.game_logs import mlb_game_log_types_present

    assert mlb_game_log_types_present(games) == {"hitting", "pitching"}


def test_mlb_default_game_log_type_pitcher_legacy_hitting_tag():
    from src.sports.game_logs import (
        MLB_LOG_HITTING,
        MLB_LOG_PITCHING,
        mlb_default_game_log_type,
    )

    games = pd.DataFrame([{"log_type": "hitting", "runs": None, "fantasy_points": 20.0}])
    assert (
        mlb_default_game_log_type(pd.DataFrame(), games, primary_position="SP")
        == MLB_LOG_PITCHING
    )


def test_filter_mlb_pitcher_legacy_hitting_tag():
    games = pd.DataFrame(
        [
            {
                "game_id": "1",
                "log_type": "hitting",
                "runs": None,
                "innings_pitched": None,
                "fantasy_points": 20.0,
            }
        ]
    )
    out = filter_game_log_for_profile(games, "mlb", "SP", log_type="pitching")
    assert len(out) == 1


def test_filter_mlb_game_log_by_role():
    games = pd.DataFrame(
        [
            {"game_id": "1", "log_type": "hitting", "runs": 1, "fantasy_points": 5.0},
            {"game_id": "1", "log_type": "pitching", "innings_pitched": 6, "fantasy_points": 20.0},
        ]
    )
    hit = filter_game_log_for_profile(games, "mlb", "DH")
    assert len(hit) == 1
    assert hit.iloc[0]["log_type"] == "hitting"
