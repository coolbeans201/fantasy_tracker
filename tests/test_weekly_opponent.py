import pandas as pd

from src.db.maintenance import _opponent_lookup_from_nflverse


def test_opponent_lookup_player_weekly():
    raw = pd.DataFrame(
        {
            "player_id": ["p1", "p1"],
            "season": [2023, 2023],
            "week": [1, 1],
            "season_type": ["REG", "POST"],
            "team": ["KC", "KC"],
            "opponent_team": ["DET", "BUF"],
        }
    )
    out = _opponent_lookup_from_nflverse(raw, team_level=False)
    assert len(out) == 1
    assert out.iloc[0]["opponent"] == "DET"


def test_opponent_lookup_team_weekly():
    raw = pd.DataFrame(
        {
            "season": [2022],
            "week": [5],
            "season_type": ["REG"],
            "recent_team": ["DEN"],
            "opponent_team": ["LAC"],
        }
    )
    out = _opponent_lookup_from_nflverse(raw, team_level=True)
    assert out.iloc[0]["team"] == "DEN"
    assert out.iloc[0]["opponent"] == "LAC"
