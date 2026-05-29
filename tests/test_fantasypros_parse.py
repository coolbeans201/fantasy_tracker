from src.rankings.fantasypros_parse import (
    consensus_rankings_to_draft_ecr,
    fp_player_display_name,
    players_list_to_draft_ecr,
)


def test_consensus_rankings_nba():
    payload = {
        "players": [
            {
                "player_id": 2343,
                "player_name": "Nikola Jokic",
                "player_team_id": "DEN",
                "player_positions": "C",
                "rank_ave": "1.5",
                "rank_std": "0.5",
            }
        ]
    }
    df = consensus_rankings_to_draft_ecr(payload, sport_id="nba", season=2025)
    assert len(df) == 1
    assert df.iloc[0]["ecr_rank"] == 2
    assert df.iloc[0]["position"] == "C"
    assert df.iloc[0]["fantasypros_id"] == "2343"


def test_fp_player_display_name_from_reverse():
    assert (
        fp_player_display_name({"reverse_name": "Jordan, Michael"})
        == "Michael Jordan"
    )


def test_fp_player_display_name_nested_player():
    assert (
        fp_player_display_name(
            {
                "player": {"player_name": "Kevin Durant", "team_id": "OKC"},
                "player_id": 99,
            }
        )
        == "Kevin Durant"
    )


def test_players_list_mlb_rank_ecr():
    payload = {
        "players": [
            {
                "player_id": 3020,
                "player_name": "Mike Trout",
                "team_id": "LAA",
                "position_id": "OF",
                "rank_ecr": 12,
            }
        ]
    }
    df = players_list_to_draft_ecr(payload, sport_id="mlb", season=2024)
    assert len(df) == 1
    assert df.iloc[0]["ecr_rank"] == 12
    assert df.iloc[0]["position"] == "OF"
