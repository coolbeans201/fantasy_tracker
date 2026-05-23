"""Tests for FantasyPros ranking normalization."""

import pandas as pd

from src.rankings.normalize import filter_redraft_rows, prepare_draft_ecr


def test_filter_redraft_keeps_rp():
    raw = pd.DataFrame(
        [
            {
                "ecr_type": "rp",
                "page_type": "wr",
                "pos": "WR",
                "player": "Test Player",
                "id": "1",
                "ecr": 12,
                "season": 2023,
            },
            {
                "ecr_type": "dyn",
                "page_type": "wr",
                "pos": "WR",
                "player": "Other",
                "id": "2",
                "ecr": 5,
                "season": 2023,
            },
        ]
    )
    out = filter_redraft_rows(raw)
    assert len(out) == 1
    assert out.iloc[0]["player_name"] == "Test Player"


def test_prepare_draft_dedupes_latest_scrape():
    raw = pd.DataFrame(
        [
            {
                "ecr_type": "rp",
                "page_type": "rb",
                "pos": "RB",
                "player": "A",
                "id": "99",
                "ecr": 20,
                "season": 2022,
                "scrape_date": "2022-08-01",
            },
            {
                "ecr_type": "rp",
                "page_type": "rb",
                "pos": "RB",
                "player": "A",
                "id": "99",
                "ecr": 18,
                "season": 2022,
                "scrape_date": "2022-09-01",
            },
        ]
    )
    out = prepare_draft_ecr(raw)
    assert len(out) == 1
    assert int(out.iloc[0]["ecr_rank"]) == 18
