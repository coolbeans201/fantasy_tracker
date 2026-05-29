import pandas as pd

from src.rankings.sport_map_players import (
    _fuzzy_match_player_id,
    fp_name_overlap_rate,
    fp_season_looks_mismatched,
)


def test_fuzzy_match_ignores_wrong_fp_team():
    """FP team must not narrow the pool away from the stats stint team."""
    lookup = pd.DataFrame(
        [
            {
                "player_id": "2544",
                "player_name": "LeBron James",
                "position": "SF",
                "team": "MIA",
            },
            {
                "player_id": "9999",
                "player_name": "Iman Shumpert",
                "position": "SG",
                "team": "NYK",
            },
        ]
    )
    pid = _fuzzy_match_player_id(
        "LeBron James",
        lookup,
        position="SF",
        fuzzy_threshold=88,
    )
    assert pid == "2544"


def test_fp_season_mismatch_modern_names_vs_2012_stats():
    raw = pd.DataFrame(
        {
            "fantasypros_id": ["1", "2", "3"],
            "player_name": ["Nikola Jokic", "Victor Wembanyama", "Shai Gilgeous-Alexander"],
        }
    )
    lookup = pd.DataFrame(
        {
            "player_id": [str(i) for i in range(60)],
            "player_name": [f"Player {i}" for i in range(60)],
            "position": ["SF"] * 60,
            "team": ["LAL"] * 60,
        }
    )
    lookup.loc[0, "player_name"] = "LeBron James"
    rate = fp_name_overlap_rate(raw, lookup, sample_size=10)
    assert rate is not None and rate < 0.2
    mismatch, _ = fp_season_looks_mismatched(
        raw, lookup, min_stats_players=50, overlap_threshold=0.2
    )
    assert mismatch is True


def test_fuzzy_match_duncan():
    lookup = pd.DataFrame(
        [
            {
                "player_id": "1495",
                "player_name": "Tim Duncan",
                "position": "PF",
                "team": "SAS",
            },
        ]
    )
    pid = _fuzzy_match_player_id(
        "Tim Duncan",
        lookup,
        position="PF",
        fuzzy_threshold=88,
    )
    assert pid == "1495"
