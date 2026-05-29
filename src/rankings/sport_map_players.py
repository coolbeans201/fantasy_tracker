"""Map FantasyPros IDs to sport season-stats player_id."""

from __future__ import annotations

import duckdb
import pandas as pd
from rapidfuzz import fuzz, process

from src.sports.player_seasons import stats_table
from src.text_encoding import fold_for_search, normalize_unicode_text


def sport_season_player_lookup(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
) -> pd.DataFrame:
    table = stats_table(sport_id)
    df = conn.execute(
        f"""
        SELECT DISTINCT
            player_id,
            player_name,
            position,
            season,
            team
        FROM {table}
        WHERE season = ?
          AND player_id IS NOT NULL
        """,
        [int(season)],
    ).df()
    if df.empty:
        return df
    df.columns = [str(c).lower() for c in df.columns]
    return df


def fp_name_overlap_rate(
    rankings: pd.DataFrame,
    lookup: pd.DataFrame,
    *,
    sample_size: int = 40,
) -> float | None:
    """
    Share of top FP names that appear exactly in the season stats name list.

    Low overlap with a full stats table usually means the API returned the wrong era
    (e.g. current rankings for a historical season URL).
    """
    if rankings.empty or lookup.empty or "player_name" not in rankings.columns:
        return None

    id_col = "fantasypros_id" if "fantasypros_id" in rankings.columns else None
    if id_col:
        sample = rankings.drop_duplicates(subset=[id_col], keep="first")
    else:
        sample = rankings
    sample = sample.head(sample_size)

    stats_names = set(lookup["player_name"].astype(str).map(_fold_name))
    checked = 0
    hits = 0
    for _, row in sample.iterrows():
        folded = _fold_name(str(row.get("player_name") or ""))
        if not folded:
            continue
        checked += 1
        if folded in stats_names:
            hits += 1
    if checked == 0:
        return None
    return hits / checked


def fp_season_looks_mismatched(
    rankings: pd.DataFrame,
    lookup: pd.DataFrame,
    *,
    min_stats_players: int = 50,
    overlap_threshold: float = 0.20,
    sample_size: int = 40,
) -> tuple[bool, float | None]:
    """True when FP names barely overlap ingested stats for the requested season."""
    stats_players = int(lookup["player_id"].nunique()) if not lookup.empty else 0
    if stats_players < min_stats_players:
        return False, None
    rate = fp_name_overlap_rate(rankings, lookup, sample_size=sample_size)
    if rate is None:
        return False, None
    return rate < overlap_threshold, rate


def season_lookup_stats(lookup: pd.DataFrame) -> dict[str, int]:
    if lookup.empty:
        return {"lookup_rows": 0, "lookup_players": 0}
    return {
        "lookup_rows": len(lookup),
        "lookup_players": int(lookup["player_id"].nunique()),
    }


def _narrow_lookup_pool(
    lookup: pd.DataFrame,
    *,
    position: str,
) -> pd.DataFrame:
    """
    Optional position hint only.

    Team is intentionally not used: FantasyPros team labels often disagree with
    the franchise on our stats row for the same season (trades, FA tags, stale FP data).
    """
    pool = lookup
    pos = str(position or "").strip().upper()
    if pos:
        pos_pool = pool[pool["position"].astype(str).str.upper() == pos]
        if not pos_pool.empty:
            pool = pos_pool
    return pool


def _fold_name(value: str) -> str:
    return fold_for_search(normalize_unicode_text(value))


def _fuzzy_match_player_id(
    name: str,
    lookup: pd.DataFrame,
    *,
    position: str,
    fuzzy_threshold: int,
) -> str | None:
    query = _fold_name(name)
    if not query:
        return None

    pool = _narrow_lookup_pool(lookup, position=position)
    name_pool = pool.drop_duplicates(subset=["player_name"])
    folded = name_pool["player_name"].astype(str).map(_fold_name).tolist()
    if not folded:
        return None
    match = process.extractOne(
        query,
        folded,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=fuzzy_threshold,
    )
    if not match:
        return None
    hit = name_pool[name_pool["player_name"].astype(str).map(_fold_name) == match[0]]
    if hit.empty:
        return None
    return str(hit["player_id"].iloc[0]).strip()


def attach_sport_player_ids(
    rankings: pd.DataFrame,
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
    *,
    fuzzy_threshold: int = 88,
) -> tuple[pd.DataFrame, int]:
    """Add ``player_id`` using name/team/position fuzzy match against season stats."""
    if rankings.empty:
        return rankings, 0

    out = rankings.copy()
    out["player_id"] = pd.NA
    if "fantasypros_id" in out.columns:
        out["fantasypros_id"] = out["fantasypros_id"].astype(str).str.strip()

    lookup = sport_season_player_lookup(conn, sport_id, season)
    if lookup.empty:
        return pd.DataFrame(), len(out)

    sid = sport_id.strip().lower()
    id_col = "fantasypros_id" if "fantasypros_id" in out.columns else None
    if id_col:
        keys = out.drop_duplicates(subset=[id_col], keep="first")
    else:
        keys = out.drop_duplicates(
            subset=["player_name", "team", "position"], keep="first"
        )

    fp_to_player: dict[str, str] = {}
    for _, row in keys.iterrows():
        name = normalize_unicode_text(str(row.get("player_name") or "").strip())
        if not name:
            continue
        pos = str(row.get("position") or "")
        pid = _fuzzy_match_player_id(
            name,
            lookup,
            position=pos,
            fuzzy_threshold=fuzzy_threshold,
        )
        if not pid and pos:
            pid = _fuzzy_match_player_id(
                name,
                lookup,
                position="",
                fuzzy_threshold=fuzzy_threshold,
            )
        if not pid:
            continue
        if id_col:
            fp_to_player[str(row[id_col])] = pid
        else:
            fp_to_player[
                (
                    name,
                    str(row.get("team") or ""),
                    str(row.get("position") or ""),
                )
            ] = pid

    if id_col:
        out["player_id"] = out[id_col].map(fp_to_player)
    else:
        for idx, row in out.iterrows():
            key = (
                normalize_unicode_text(str(row.get("player_name") or "").strip()),
                str(row.get("team") or ""),
                str(row.get("position") or ""),
            )
            out.at[idx, "player_id"] = fp_to_player.get(key)

    unmapped = int(out["player_id"].isna().sum())
    mapped = out[out["player_id"].notna()].copy()
    mapped["player_id"] = mapped["player_id"].astype(str).str.strip()
    return mapped, unmapped
