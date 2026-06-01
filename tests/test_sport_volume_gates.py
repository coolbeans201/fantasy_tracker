import pandas as pd

from src.analytics.sport_variance import qualifies_for_peer_z_sport
from src.settings import get_min_games_default


def test_mlb_hitter_uses_pa_default():
    default_pa = get_min_games_default("mlb")
    row_low = pd.Series({"position": "OF", "plate_appearances": default_pa - 1, "games": 100})
    row_ok = pd.Series({"position": "OF", "plate_appearances": default_pa, "games": 100})
    assert qualifies_for_peer_z_sport(row_low, "mlb") is False
    assert qualifies_for_peer_z_sport(row_ok, "mlb") is True


def test_mlb_pitcher_uses_ip_gate_not_pa_slider():
    row = pd.Series(
        {"position": "SP", "plate_appearances": 0, "games": 30, "innings_pitched": 60}
    )
    assert qualifies_for_peer_z_sport(row, "mlb", min_games=200) is True
