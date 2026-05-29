"""Compare-page cohort compatibility (within sport)."""

from __future__ import annotations

from collections.abc import Callable

import duckdb


def _distinct_cohorts(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    player_id: str,
    cohort_fn,
    *,
    season: int | None,
    seasons: list[int] | None,
) -> set[str]:
    params: list = [str(player_id).strip()]
    query = f"""
        SELECT DISTINCT position
        FROM {table}
        WHERE player_id = ?
    """
    if season is not None:
        query += " AND season = ?"
        params.append(int(season))
    elif seasons:
        placeholders = ", ".join("?" * len(seasons))
        query += f" AND season IN ({placeholders})"
        params.extend(int(s) for s in seasons)

    rows = conn.execute(query, params).fetchall()
    return {cohort_fn(r[0]) for r in rows if r[0] is not None}


def mlb_compare_cohort_hint_from_label(label: str | None) -> str | None:
    from src.sports.mlb.positions import COMPARE_GROUP_HITTER, COMPARE_GROUP_PITCHER

    choice = str(label or "").strip()
    if choice == "Pitchers":
        return COMPARE_GROUP_PITCHER
    if choice == "Hitters":
        return COMPARE_GROUP_HITTER
    return None


def nhl_compare_cohort_hint_from_label(label: str | None) -> str | None:
    from src.sports.nhl.positions import COMPARE_GROUP_GOALIE, COMPARE_GROUP_SKATER

    choice = str(label or "").strip()
    if choice == "Goalies":
        return COMPARE_GROUP_GOALIE
    if choice == "Skaters":
        return COMPARE_GROUP_SKATER
    return None


def compare_cohorts_compatible(
    sport_id: str,
    position_a: str | None,
    position_b: str | None,
    *,
    conn: duckdb.DuckDBPyConnection | None = None,
    player_a: str | None = None,
    player_b: str | None = None,
    season: int | None = None,
    seasons: list[int] | None = None,
    cohort_hint: str | None = None,
) -> tuple[bool, str | None]:
    sid = str(sport_id).strip().lower()
    if sid == "mlb":
        from src.sports.mlb.positions import compare_cohort, compare_incompatible_message

        if conn is not None and player_a and player_b:
            ca = _distinct_cohorts(
                conn,
                "mlb_player_season_stats",
                player_a,
                compare_cohort,
                season=season,
                seasons=seasons,
            )
            cb = _distinct_cohorts(
                conn,
                "mlb_player_season_stats",
                player_b,
                compare_cohort,
                season=season,
                seasons=seasons,
            )
            if cohort_hint:
                label = (
                    "hitters"
                    if cohort_hint == "hitter"
                    else "pitchers"
                )
                if cohort_hint not in ca or cohort_hint not in cb:
                    return (
                        False,
                        f"Both players need **{label}** stats in this compare window.",
                    )
            if ca.isdisjoint(cb):
                a = next(iter(ca)) if ca else compare_cohort(position_a)
                b = next(iter(cb)) if cb else compare_cohort(position_b)
                return False, compare_incompatible_message(a, b)
            return True, None

        ca = compare_cohort(position_a)
        cb = compare_cohort(position_b)
        if ca != cb:
            return False, compare_incompatible_message(ca, cb)
    elif sid == "nhl":
        from src.sports.nhl.positions import compare_cohort, compare_incompatible_message

        if conn is not None and player_a and player_b:
            ca = _distinct_cohorts(
                conn,
                "nhl_player_season_stats",
                player_a,
                compare_cohort,
                season=season,
                seasons=seasons,
            )
            cb = _distinct_cohorts(
                conn,
                "nhl_player_season_stats",
                player_b,
                compare_cohort,
                season=season,
                seasons=seasons,
            )
            if cohort_hint:
                label = (
                    "goalies"
                    if cohort_hint == "goalie"
                    else "skaters"
                )
                if cohort_hint not in ca or cohort_hint not in cb:
                    return (
                        False,
                        f"Both players need **{label}** stats in this compare window.",
                    )
            if ca.isdisjoint(cb):
                a = next(iter(ca)) if ca else compare_cohort(position_a)
                b = next(iter(cb)) if cb else compare_cohort(position_b)
                return False, compare_incompatible_message(a, b)
            return True, None

        ca = compare_cohort(position_a)
        cb = compare_cohort(position_b)
        if ca != cb:
            return False, compare_incompatible_message(ca, cb)
    return True, None


def filter_compare_season_rows(
    df,
    sport_id: str,
    *,
    cohort_hint: str | None,
):
    """Drop rows from the other cohort (e.g. pitching rows when comparing hitters)."""
    import pandas as pd

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return df
    if not cohort_hint or "position" not in df.columns:
        return df

    sid = str(sport_id).strip().lower()
    if sid == "mlb":
        from src.sports.mlb.positions import (
            COMPARE_GROUP_HITTER,
            COMPARE_GROUP_PITCHER,
            is_pitcher_position,
        )

        if cohort_hint == COMPARE_GROUP_PITCHER:
            return df[df["position"].map(is_pitcher_position)].copy()
        if cohort_hint == COMPARE_GROUP_HITTER:
            return df[~df["position"].map(is_pitcher_position)].copy()
    elif sid == "nhl":
        from src.sports.nhl.positions import (
            COMPARE_GROUP_GOALIE,
            COMPARE_GROUP_SKATER,
            is_goalie_position,
        )

        if cohort_hint == COMPARE_GROUP_GOALIE:
            return df[df["position"].map(is_goalie_position)].copy()
        if cohort_hint == COMPARE_GROUP_SKATER:
            return df[~df["position"].map(is_goalie_position)].copy()
    return df


_MLB_COMPARE_SUM_COLS = (
    "games",
    "plate_appearances",
    "runs",
    "home_runs",
    "rbi",
    "stolen_bases",
    "walks",
    "strikeouts_bat",
    "wins",
    "strikeouts_pitch",
    "saves",
    "innings_pitched",
)


def _combine_compare_teams(series) -> str:
    import pandas as pd

    teams = sorted(
        {
            str(t).strip()
            for t in series.dropna()
            if str(t).strip() and str(t).strip().lower() not in {"nan", "none"}
        }
    )
    if not teams:
        return ""
    if len(teams) == 1:
        return teams[0]
    return "2TM"


def aggregate_mlb_compare_by_season(df, cohort_hint: str | None):
    """One row per season after cohort filter (sums multi-team hitter stints)."""
    import pandas as pd

    from src.sports.mlb.positions import (
        COMPARE_GROUP_HITTER,
        COMPARE_GROUP_PITCHER,
        is_pitcher_position,
    )
    from src.sports.mlb.scoring import compute_hitter_fp, compute_pitcher_fp

    if (
        df is None
        or (isinstance(df, pd.DataFrame) and df.empty)
        or cohort_hint not in (COMPARE_GROUP_HITTER, COMPARE_GROUP_PITCHER)
        or "season" not in df.columns
    ):
        return df
    if df.groupby("season").size().max() <= 1:
        return df

    sum_cols = [c for c in _MLB_COMPARE_SUM_COLS if c in df.columns]
    agg: dict[str, str | Callable] = {c: "sum" for c in sum_cols}
    for col in ("player_id", "player_name"):
        if col in df.columns:
            agg[col] = "first"
    if "team" in df.columns:
        agg["team"] = _combine_compare_teams

    grouped = df.groupby("season", as_index=False).agg(agg)

    def _pick_position(g: pd.DataFrame) -> str:
        if cohort_hint == COMPARE_GROUP_PITCHER:
            pitchers = [p for p in g["position"] if is_pitcher_position(p)]
            return str(pitchers[0] if pitchers else g["position"].iloc[0])
        hitters = [p for p in g["position"] if not is_pitcher_position(p)]
        return str(hitters[0] if hitters else g["position"].iloc[0])

    grouped["position"] = [
        _pick_position(df[df["season"] == int(season)])
        for season in grouped["season"]
    ]

    if cohort_hint == COMPARE_GROUP_PITCHER:
        fp = compute_pitcher_fp(grouped)
    else:
        fp = compute_hitter_fp(grouped)
    grouped["fantasy_points"] = fp
    if "fantasy_points_espn" in grouped.columns:
        grouped["fantasy_points_espn"] = fp
    return grouped.sort_values("season").reset_index(drop=True)


def prepare_compare_season_rows(
    df,
    sport_id: str,
    *,
    cohort_hint: str | None,
):
    """Filter to cohort, then collapse duplicate seasons (MLB two-way / multi-team)."""
    out = filter_compare_season_rows(df, sport_id, cohort_hint=cohort_hint)
    if str(sport_id).strip().lower() == "mlb":
        out = aggregate_mlb_compare_by_season(out, cohort_hint)
    return out
