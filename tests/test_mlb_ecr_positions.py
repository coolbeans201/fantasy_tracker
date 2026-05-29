"""MLB draft ECR SP vs RP handling."""

import pandas as pd

from src.rankings.fantasypros_parse import consensus_rankings_to_draft_ecr
from src.rankings.mlb_ecr_positions import sync_mlb_pitcher_ecr_positions
from src.sports.mlb.positions import normalize_mlb_ecr_position


def test_normalize_mlb_ecr_position_uses_sp_rp_bucket():
    assert normalize_mlb_ecr_position("P", position_bucket="RP") == "RP"
    assert normalize_mlb_ecr_position("SP,RP", position_bucket="SP") == "SP"


def test_consensus_mlb_sp_bucket_forces_sp_position():
    payload = {
        "players": [
            {
                "player_id": 99,
                "player_name": "Closer X",
                "player_positions": "RP",
                "rank_ave": "3",
            }
        ]
    }
    df = consensus_rankings_to_draft_ecr(
        payload, sport_id="mlb", season=2025, position_bucket="SP"
    )
    assert len(df) == 1
    assert df.iloc[0]["position"] == "SP"
    assert int(df.iloc[0]["ecr_rank"]) == 3


def test_sync_mlb_pitcher_ecr_positions_from_stats():
    rankings = pd.DataFrame(
        [
            {
                "player_id": "123",
                "player_name": "Reliever",
                "position": "SP",
                "ecr_rank": 5,
            }
        ]
    )
    lookup = pd.DataFrame(
        [
            {
                "player_id": "123",
                "position": "RP",
                "games": 65,
            }
        ]
    )

    class _Conn:
        def execute(self, *_args, **_kwargs):
            class _R:
                def df(self):
                    return lookup.copy()

            return _R()

    out, n = sync_mlb_pitcher_ecr_positions(rankings, _Conn(), 2025)
    assert n == 1
    assert out.iloc[0]["position"] == "RP"
