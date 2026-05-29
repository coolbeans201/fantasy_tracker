import pandas as pd

from src.rankings.fantasypros_positions import (
    _primary_position_from_fp_row,
    _should_overlay_mlb_hitter,
    _should_overlay_nba,
    overlay_positions_on_frame,
)


def test_fp_nba_curry_primary_pg():
    row = {
        "player_name": "Stephen Curry",
        "position_id": "PG,SG",
        "positions": ["PG", "SG"],
        "team_id": "GSW",
    }
    assert _primary_position_from_fp_row("nba", row) == "PG"


def test_overlay_nba_fixes_sg_with_fp_pg():
    assert _should_overlay_nba("SG", "PG") is True
    assert _should_overlay_nba("PG", "PG") is False
    assert _should_overlay_nba(None, "C") is True


def test_fp_mlb_harper_rf():
    row = {
        "position_id": "RF",
        "positions": ["RF"],
        "primary_position": "OF",
    }
    assert _primary_position_from_fp_row("mlb", row) == "RF"


def test_mlb_overlay_rejects_pitcher_fp_position():
    assert _should_overlay_mlb_hitter("H", "SP") is False


def test_mlb_overlay_skips_hitter_when_sp_row_exists(monkeypatch):
    frame = pd.DataFrame(
        [
            {
                "player_id": 110683,
                "player_name": "Test Player",
                "team": "SEATTLE",
                "position": "H",
                "season": 2008,
            },
            {
                "player_id": 110683,
                "player_name": "Test Player",
                "team": "SEATTLE",
                "position": "SP",
                "season": 2008,
            },
        ]
    )
    fp_df = pd.DataFrame(
        [{"player_name": "Test Player", "team": "SEATTLE", "position": "SP"}]
    )

    monkeypatch.setattr(
        "src.rankings.fantasypros_positions.fantasypros_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "src.rankings.fantasypros_positions.fetch_fp_players_frame",
        lambda *_a, **_k: fp_df,
    )
    monkeypatch.setattr(
        "src.rankings.fantasypros_positions._match_fp_position",
        lambda *_a, **_k: "SP",
    )

    out, updated = overlay_positions_on_frame(frame, "mlb")
    assert updated == 0
    assert out.loc[out["position"] == "H", "position"].iloc[0] == "H"
    assert out.loc[out["position"] == "SP", "position"].iloc[0] == "SP"
