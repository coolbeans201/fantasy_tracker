from src.rankings.fantasypros_limits import (
    FP_SPORT_DRAFT_ECR_MIN_SEASON,
    sport_draft_ecr_supported,
)


def test_sport_draft_ecr_supported_from_2012():
    assert sport_draft_ecr_supported("nba", FP_SPORT_DRAFT_ECR_MIN_SEASON)
    assert not sport_draft_ecr_supported("nba", 2011)
    assert not sport_draft_ecr_supported("nfl", 2005)
