"""Team D/ST stat columns and nflverse team-stats mapping."""

from __future__ import annotations

import pandas as pd

from src.scoring.special import DST_FP_COLUMN

DST_STAT_COLUMNS = [
    "sacks",
    "def_interceptions",
    "fumble_recoveries",
    "safeties",
    "blocked_kicks",
    "def_touchdowns",
    "return_touchdowns",
    "points_allowed",
    "yards_allowed",
]

# nflverse team stats -> schema
NFLVERSE_TEAM_DST_MAP: dict[str, str] = {
    "team": "team",
    "recent_team": "team",
    "opponent_team": "opponent",
    "opponent": "opponent",
    "season": "season",
    "week": "week",
    "season_type": "season_type",
    "sacks": "sacks",
    "def_sacks": "sacks",
    "interceptions": "def_interceptions",
    "def_interceptions": "def_interceptions",
    "defensive_interceptions": "def_interceptions",
    "fumble_recovery": "fumble_recoveries",
    "fumble_recoveries": "fumble_recoveries",
    "fumbles_recovered": "fumble_recoveries",
    "def_fumble_recoveries": "fumble_recoveries",
    "safeties": "safeties",
    "def_safeties": "safeties",
    "blocked_kicks": "blocked_kicks",
    "fg_blocked": "blocked_kicks",
    "def_blocked_kicks": "blocked_kicks",
    "def_touchdowns": "def_touchdowns",
    "def_tds": "def_touchdowns",
    "defensive_touchdowns": "def_touchdowns",
    "special_teams_tds": "return_touchdowns",
    "return_touchdowns": "return_touchdowns",
    "return_tds": "return_touchdowns",
    "opponent_score": "points_allowed",
    "opponent_total": "points_allowed",
    "points_allowed": "points_allowed",
    "opp_points": "points_allowed",
    "opp_score": "points_allowed",
    "yards_allowed": "yards_allowed",
    "opp_yards": "yards_allowed",
    "opponent_yards": "yards_allowed",
    "total_yards_allowed": "yards_allowed",
}


def sql_dst_stat_select() -> str:
    return ", ".join(DST_STAT_COLUMNS)


def _as_dataframe(frame) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        return frame
    if hasattr(frame, "to_pandas"):
        return frame.to_pandas()
    return pd.DataFrame(frame)


def points_allowed_from_schedules(schedules) -> pd.DataFrame:
    """
    One row per (season, week, team) with opponent points scored (REG only).
    nflverse schedules: home_team/away_team and home_score/away_score.
    """
    df = _as_dataframe(schedules)
    empty = pd.DataFrame(columns=["season", "week", "team", "points_allowed"])
    if df.empty:
        return empty

    if "season_type" in df.columns:
        df = df[df["season_type"].astype(str).str.upper() == "REG"]
    elif "game_type" in df.columns:
        df = df[df["game_type"].astype(str).str.upper() == "REG"]

    home_col = "home_team" if "home_team" in df.columns else None
    away_col = "away_team" if "away_team" in df.columns else None
    if not home_col or not away_col:
        return empty
    for col in ("home_score", "away_score", "season", "week"):
        if col not in df.columns:
            return empty

    df = df.copy()
    df["season"] = pd.to_numeric(df["season"], errors="coerce")
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    home_score = pd.to_numeric(df["home_score"], errors="coerce")
    away_score = pd.to_numeric(df["away_score"], errors="coerce")

    home_rows = pd.DataFrame(
        {
            "season": df["season"],
            "week": df["week"],
            "team": df[home_col].astype(str).str.strip(),
            "points_allowed": away_score,
        }
    )
    away_rows = pd.DataFrame(
        {
            "season": df["season"],
            "week": df["week"],
            "team": df[away_col].astype(str).str.strip(),
            "points_allowed": home_score,
        }
    )
    out = pd.concat([home_rows, away_rows], ignore_index=True)
    out = out[out["points_allowed"].notna() & out["team"].notna() & (out["team"] != "")]
    return out.drop_duplicates(subset=["season", "week", "team"], keep="first")


def yards_allowed_from_team_stats(team_stats) -> pd.DataFrame:
    """
    Opponent offensive yards (pass + rush) allowed per team-week (REG only).
    Uses nflverse team stats: join each defense to its opponent's box-score yards.
    """
    df = _as_dataframe(team_stats)
    empty = pd.DataFrame(columns=["season", "week", "team", "yards_allowed"])
    if df.empty:
        return empty

    if "season_type" in df.columns:
        df = df[df["season_type"].astype(str).str.upper() == "REG"]

    team_col = "team" if "team" in df.columns else "recent_team"
    opp_col = "opponent_team" if "opponent_team" in df.columns else "opponent"
    if team_col not in df.columns or opp_col not in df.columns:
        return empty

    df = df.copy()
    df["season"] = pd.to_numeric(df["season"], errors="coerce")
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    df["team"] = df[team_col].astype(str).str.strip()
    df["opponent"] = df[opp_col].astype(str).str.strip()
    pass_y = pd.to_numeric(df.get("passing_yards", 0), errors="coerce").fillna(0)
    rush_y = pd.to_numeric(df.get("rushing_yards", 0), errors="coerce").fillna(0)
    df["_off_yards"] = pass_y + rush_y

    offense = df[["season", "week", "team", "_off_yards"]].copy()
    keys = df[["season", "week", "team", "opponent"]].drop_duplicates()
    if "game_id" in df.columns:
        keys = df[["season", "week", "game_id", "team", "opponent"]].drop_duplicates()
        offense["game_id"] = df["game_id"]
        opp = offense.rename(columns={"team": "opponent", "_off_yards": "yards_allowed"})
        merged = keys.merge(
            opp,
            on=["season", "week", "game_id", "opponent"],
            how="left",
        )
    else:
        opp = offense.rename(columns={"team": "opponent", "_off_yards": "yards_allowed"})
        merged = keys.merge(opp, on=["season", "week", "opponent"], how="left")

    out = merged[["season", "week", "team", "yards_allowed"]]
    out = out[out["yards_allowed"].notna() & out["team"].notna() & (out["team"] != "")]
    return out.drop_duplicates(subset=["season", "week", "team"], keep="first")


def attach_opponent_allowed_stats(
    team_dst: pd.DataFrame,
    *,
    schedules=None,
    team_stats=None,
) -> pd.DataFrame:
    """Attach points allowed (schedules) and yards allowed (opponent team stats)."""
    out = team_dst.copy()
    out["season"] = pd.to_numeric(out["season"], errors="coerce")
    out["week"] = pd.to_numeric(out["week"], errors="coerce")
    out["team"] = out["team"].astype(str).str.strip()

    if schedules is not None:
        pa = points_allowed_from_schedules(schedules)
        out = out.drop(columns=["points_allowed"], errors="ignore")
        if not pa.empty:
            out = out.merge(pa, on=["season", "week", "team"], how="left")

    if team_stats is not None:
        ya = yards_allowed_from_team_stats(team_stats)
        out = out.drop(columns=["yards_allowed"], errors="ignore")
        if not ya.empty:
            out = out.merge(ya, on=["season", "week", "team"], how="left")

    for col in ("points_allowed", "yards_allowed"):
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    return out


def attach_points_allowed(team_dst: pd.DataFrame, schedules) -> pd.DataFrame:
    """Merge schedule-derived points allowed onto team-week D/ST rows."""
    return attach_opponent_allowed_stats(team_dst, schedules=schedules)


def build_team_dst_season_aggregates(weekly: pd.DataFrame) -> pd.DataFrame:
    """Sum weekly D/ST stats and fantasy points to season totals."""
    stat_cols = [c for c in DST_STAT_COLUMNS if c in weekly.columns]
    sum_agg = {c: (c, "sum") for c in stat_cols} | {DST_FP_COLUMN: (DST_FP_COLUMN, "sum")}

    season = (
        weekly.groupby(["team", "season"], as_index=False)
        .agg(games=("week", "nunique"), **sum_agg)
    )

    best_rows = []
    for (team, yr), group in weekly.groupby(["team", "season"]):
        idx = group[DST_FP_COLUMN].idxmax()
        if pd.isna(idx):
            continue
        row = group.loc[idx]
        best_rows.append(
            {
                "team": team,
                "season": yr,
                "best_week": row["week"],
                "best_week_fp": row[DST_FP_COLUMN],
            }
        )
    if best_rows:
        season = season.merge(pd.DataFrame(best_rows), on=["team", "season"], how="left")

    return season
