"""Compare-page cohort compatibility (within sport)."""

from __future__ import annotations

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
            return df[df["position"].map(is_pitcher_position)]
        if cohort_hint == COMPARE_GROUP_HITTER:
            return df[~df["position"].map(is_pitcher_position)]
    elif sid == "nhl":
        from src.sports.nhl.positions import (
            COMPARE_GROUP_GOALIE,
            COMPARE_GROUP_SKATER,
            is_goalie_position,
        )

        if cohort_hint == COMPARE_GROUP_GOALIE:
            return df[df["position"].map(is_goalie_position)]
        if cohort_hint == COMPARE_GROUP_SKATER:
            return df[~df["position"].map(is_goalie_position)]
    return df
