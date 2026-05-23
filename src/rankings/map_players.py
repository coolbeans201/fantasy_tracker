"""Map FantasyPros rankings rows to fantasy_tracker player_id."""

from __future__ import annotations

import pandas as pd
from rapidfuzz import fuzz, process

from src.entities import make_dst_entity_id
from src.positions import DST_POSITION
from src.rankings.normalize import entity_id_from_ranking_row


def load_fantasypros_to_gsis() -> pd.DataFrame:
    """fantasypros_id -> gsis_id (our player_id)."""
    import nflreadpy as nfl

    raw = nfl.load_ff_playerids()
    if hasattr(raw, "to_pandas"):
        ids = raw.to_pandas()
    else:
        ids = pd.DataFrame(raw)

    ids.columns = [str(c).strip().lower() for c in ids.columns]
    fp_col = None
    for candidate in ("fantasypros_id", "fantasypros", "fp_id", "id_fp"):
        if candidate in ids.columns:
            fp_col = candidate
            break
    gsis_col = None
    for candidate in ("gsis_id", "player_id", "nfl_id"):
        if candidate in ids.columns:
            gsis_col = candidate
            break
    if fp_col is None or gsis_col is None:
        return pd.DataFrame(columns=["fantasypros_id", "player_id"])

    out = ids[[fp_col, gsis_col]].copy()
    out.columns = ["fantasypros_id", "player_id"]
    out["fantasypros_id"] = out["fantasypros_id"].astype(str).str.strip()
    out["player_id"] = out["player_id"].astype(str).str.strip()
    out = out[out["fantasypros_id"].notna() & out["player_id"].notna()].copy()
    out = out.drop_duplicates(subset=["fantasypros_id"], keep="first")
    return out


def season_player_lookup(conn) -> pd.DataFrame:
    """player_id, player_name, position, season for fuzzy fallback."""
    return conn.execute(
        """
        SELECT DISTINCT
            s.player_id,
            s.player_name,
            s.position,
            s.season
        FROM season_stats s
        WHERE s.player_id IS NOT NULL
        """
    ).df()


def attach_player_ids(
    rankings: pd.DataFrame,
    conn,
    fp_map: pd.DataFrame | None = None,
    *,
    fuzzy_threshold: int = 90,
) -> tuple[pd.DataFrame, int]:
    """
    Add player_id column. Returns (frame, unmapped_count).
    """
    if rankings.empty:
        return rankings, 0

    fp_map = fp_map if fp_map is not None else load_fantasypros_to_gsis()
    out = rankings.copy()
    if "fantasypros_id" in out.columns:
        out["fantasypros_id"] = out["fantasypros_id"].astype(str).str.strip()
    else:
        out["fantasypros_id"] = pd.NA

    out["player_id"] = pd.NA

    dst_mask = out["position"].astype(str).str.upper() == DST_POSITION
    out.loc[dst_mask, "player_id"] = out.loc[dst_mask].apply(
        lambda r: entity_id_from_ranking_row(r), axis=1
    )

    if not fp_map.empty and out["fantasypros_id"].notna().any():
        fp_dict = dict(zip(fp_map["fantasypros_id"], fp_map["player_id"]))
        mapped_ids = out.loc[~dst_mask, "fantasypros_id"].map(fp_dict)
        out.loc[~dst_mask, "player_id"] = out.loc[~dst_mask, "player_id"].fillna(mapped_ids)

    lookup = season_player_lookup(conn)
    if lookup.empty:
        unmapped = int(out["player_id"].isna().sum())
        return out[out["player_id"].notna()].copy(), unmapped

    lookup.columns = [str(c).lower() for c in lookup.columns]
    still_missing = out["player_id"].isna() & ~dst_mask
    if not still_missing.any():
        unmapped = int(out["player_id"].isna().sum())
        return out[out["player_id"].notna()].copy(), unmapped

    for idx, row in out[still_missing].iterrows():
        season = int(row["season"])
        pos = str(row["position"])
        name = str(row.get("player_name") or "").strip()
        if not name:
            continue
        pool = lookup[
            (lookup["season"] == season) & (lookup["position"] == pos)
        ]
        if pool.empty:
            continue
        pool = pool.drop_duplicates(subset=["player_name"], keep="first")
        choices = pool["player_name"].astype(str).tolist()
        match = process.extractOne(
            name,
            choices,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=fuzzy_threshold,
        )
        if match:
            out.at[idx, "player_id"] = pool.loc[
                pool["player_name"] == match[0], "player_id"
            ].iloc[0]

    unmapped = int(out["player_id"].isna().sum())
    return out[out["player_id"].notna()].copy(), unmapped
