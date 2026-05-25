"""D/ST points allowed from nflverse schedules."""

import pandas as pd

from src.scoring.special import apply_dst_points, compute_dst_points
from src.team_dst_columns import (
    attach_opponent_allowed_stats,
    attach_points_allowed,
    points_allowed_from_schedules,
    yards_allowed_from_team_stats,
)


def test_points_allowed_from_schedules_home_and_away():
    schedules = pd.DataFrame(
        [
            {
                "season": 2024,
                "week": 1,
                "game_type": "REG",
                "home_team": "KC",
                "away_team": "BAL",
                "home_score": 27,
                "away_score": 20,
            },
            {
                "season": 2024,
                "week": 2,
                "game_type": "REG",
                "home_team": "PHI",
                "away_team": "KC",
                "home_score": 17,
                "away_score": 22,
            },
        ]
    )
    pa = points_allowed_from_schedules(schedules)
    assert len(pa) == 4
    kc_w1 = pa[(pa["team"] == "KC") & (pa["week"] == 1)].iloc[0]
    assert kc_w1["points_allowed"] == 20
    kc_w2 = pa[(pa["team"] == "KC") & (pa["week"] == 2)].iloc[0]
    assert kc_w2["points_allowed"] == 17


def test_attach_points_allowed_updates_dst_fantasy_tiers():
    schedules = pd.DataFrame(
        [
            {
                "season": 2024,
                "week": 1,
                "game_type": "REG",
                "home_team": "DAL",
                "away_team": "NYG",
                "home_score": 28,
                "away_score": 0,
            },
        ]
    )
    weekly = pd.DataFrame(
        [
            {
                "team": "DAL",
                "season": 2024,
                "week": 1,
                "season_type": "REG",
                "sacks": 0,
                "def_interceptions": 0,
                "fumble_recoveries": 0,
                "safeties": 0,
                "blocked_kicks": 0,
                "def_touchdowns": 0,
                "return_touchdowns": 0,
                "points_allowed": 0,
            },
        ]
    )
    fixed = apply_dst_points(attach_points_allowed(weekly, schedules))
    assert fixed["points_allowed"].iloc[0] == 0
    assert compute_dst_points(fixed).iloc[0] == 10.0


def test_yards_allowed_from_opponent_team_stats():
    team_stats = pd.DataFrame(
        [
            {
                "season": 2024,
                "week": 1,
                "season_type": "REG",
                "game_id": "g1",
                "team": "DAL",
                "opponent_team": "NYG",
                "passing_yards": 280,
                "rushing_yards": 90,
            },
            {
                "season": 2024,
                "week": 1,
                "season_type": "REG",
                "game_id": "g1",
                "team": "NYG",
                "opponent_team": "DAL",
                "passing_yards": 150,
                "rushing_yards": 60,
            },
        ]
    )
    ya = yards_allowed_from_team_stats(team_stats)
    dal = ya[ya["team"] == "DAL"].iloc[0]
    assert dal["yards_allowed"] == 210


def test_attach_opponent_allowed_stats_yards_tier_scoring():
    schedules = pd.DataFrame(
        [
            {
                "season": 2024,
                "week": 1,
                "game_type": "REG",
                "home_team": "DAL",
                "away_team": "NYG",
                "home_score": 10,
                "away_score": 10,
            },
        ]
    )
    team_stats = pd.DataFrame(
        [
            {
                "season": 2024,
                "week": 1,
                "season_type": "REG",
                "game_id": "g1",
                "team": "DAL",
                "opponent_team": "NYG",
                "passing_yards": 200,
                "rushing_yards": 50,
            },
            {
                "season": 2024,
                "week": 1,
                "season_type": "REG",
                "game_id": "g1",
                "team": "NYG",
                "opponent_team": "DAL",
                "passing_yards": 100,
                "rushing_yards": 50,
            },
        ]
    )
    weekly = pd.DataFrame(
        [
            {
                "team": "DAL",
                "season": 2024,
                "week": 1,
                "season_type": "REG",
                "sacks": 0,
                "def_interceptions": 0,
                "fumble_recoveries": 0,
                "safeties": 0,
                "blocked_kicks": 0,
                "def_touchdowns": 0,
                "return_touchdowns": 0,
                "points_allowed": 0,
                "yards_allowed": 0,
            },
        ]
    )
    fixed = apply_dst_points(
        attach_opponent_allowed_stats(weekly, schedules=schedules, team_stats=team_stats)
    )
    assert fixed["yards_allowed"].iloc[0] == 150
    # PA tier 7-13 = 4, yards tier 100-199 = 3
    assert compute_dst_points(fixed).iloc[0] == 7.0
