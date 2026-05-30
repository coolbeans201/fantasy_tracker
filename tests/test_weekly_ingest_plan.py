from src.rankings.sport_ingest import (
    _consensus_query_params,
    estimate_fp_api_calls,
    plan_weekly_consensus_fetches,
    weekly_consensus_request_url,
)


def test_weekly_request_url_one_get_per_week():
    url = weekly_consensus_request_url("nba", 2025, 3)
    assert url == "NBA/2025/consensus-rankings?position=ALL&week=3"
    assert "type" not in url


def test_weekly_consensus_params_nba_no_type():
    params = _consensus_query_params("nba", position="ALL", ranking_type="weekly", week=5)
    assert params == {"position": "ALL", "week": 5}


def test_draft_consensus_params_nba_week_zero():
    params = _consensus_query_params("nba", position="ALL", ranking_type="draft")
    assert params == {"position": "ALL", "week": 0}


def test_plan_counts_one_board_per_week():
    plan = plan_weekly_consensus_fetches(
        "nba",
        2025,
        [1, 2, 3],
        positional_boards=False,
        refresh_cache=True,
    )
    assert plan["total_requests_if_no_cache"] == 3
    assert plan["positions_per_week"] == 1


def test_estimate_fp_api_calls_all_boards_only():
    est = estimate_fp_api_calls(
        "nba",
        draft=True,
        weekly_weeks=list(range(1, 27)),
        projections=True,
        positional_boards=False,
    )
    assert est["estimated_calls"] == 28  # 1 draft + 26 weekly + 1 projections
    assert est["within_daily_limit"] is True

    positional = estimate_fp_api_calls(
        "nba",
        weekly_weeks=[1],
        positional_boards=True,
    )
    assert positional["estimated_calls"] == 5  # one week × five positions
