"""Normalize DynastyProcess / FantasyPros ranking rows."""

from __future__ import annotations

import re

import pandas as pd

from src.entities import make_dst_entity_id
from src.positions import DST_POSITION, normalize_fantasy_position

_REDRAFT_ECR_TYPE = "rp"


def _to_pandas(data) -> pd.DataFrame:
    if hasattr(data, "to_pandas"):
        return data.to_pandas()
    return pd.DataFrame(data)


def _first_present(df: pd.DataFrame, names: list[str]) -> pd.Series | None:
    for name in names:
        if name in df.columns:
            return df[name]
    return None


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename = {
        "player": "player_name",
        "id": "fantasypros_id",
        "pos": "position",
        "tm": "team",
        "ecr": "ecr_rank",
        "ecr_avg": "ecr_rank",
        "sd": "ecr_sd",
        "sd_avg": "ecr_sd",
    }
    for src, dst in rename.items():
        if src in out.columns and dst not in out.columns:
            out[dst] = out[src]
    if "ecr_rank" not in out.columns and "ecr" in out.columns:
        out["ecr_rank"] = out["ecr"]
    return out


def _parse_season(df: pd.DataFrame) -> pd.Series:
    if "season" in df.columns:
        return pd.to_numeric(df["season"], errors="coerce")
    if "year" in df.columns:
        return pd.to_numeric(df["year"], errors="coerce")
    if "scrape_date" in df.columns:
        dates = pd.to_datetime(df["scrape_date"], errors="coerce")
        return dates.dt.year
    return pd.Series([pd.NA] * len(df), index=df.index)


def _parse_week(df: pd.DataFrame) -> pd.Series:
    if "week" not in df.columns:
        return pd.Series([pd.NA] * len(df), index=df.index)
    return pd.to_numeric(df["week"], errors="coerce")


def _position_series(df: pd.DataFrame) -> pd.Series:
    pos = _first_present(df, ["position", "pos"])
    if pos is None:
        return pd.Series([pd.NA] * len(df), index=df.index)
    out = pos.astype(str).str.strip().str.upper()
    out = out.replace({"DEF": DST_POSITION, "D/ST": DST_POSITION, "DST": DST_POSITION})
    return out


def _page_type_matches(row: pd.Series) -> bool:
    page = str(row.get("page_type") or "").strip().lower()
    pos = str(row.get("position") or "").strip().lower()
    if not page or not pos:
        return True
    if pos == "dst":
        return "dst" in page or "def" in page
    return page.endswith(pos)


def filter_redraft_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep redraft expert consensus rows with positional page types."""
    if df.empty:
        return df
    out = _normalize_columns(df)
    if "ecr_type" in out.columns:
        out = out[out["ecr_type"].astype(str).str.lower() == _REDRAFT_ECR_TYPE].copy()
    out["position"] = _position_series(out)
    out = out[out["position"].notna()].copy()
    mask = out.apply(_page_type_matches, axis=1)
    out = out[mask].copy()
    return out


def prepare_draft_ecr(raw: pd.DataFrame) -> pd.DataFrame:
    """Preseason draft ECR: one row per player/season/position (latest scrape)."""
    df = filter_redraft_rows(raw)
    if df.empty:
        return df

    df["season"] = _parse_season(df)
    df["week"] = _parse_week(df)
    df = df[df["season"].notna()].copy()
    df["season"] = df["season"].astype(int)

    if df["week"].notna().any():
        df = df[df["week"].isna() | (df["week"] <= 0)].copy()

    df["ecr_rank"] = pd.to_numeric(df["ecr_rank"], errors="coerce")
    df = df[df["ecr_rank"].notna()].copy()
    df["ecr_rank"] = df["ecr_rank"].round().astype(int)

    if "scrape_date" in df.columns:
        df["scrape_date"] = pd.to_datetime(df["scrape_date"], errors="coerce").dt.date
        df = df.sort_values(["season", "fantasypros_id", "position", "scrape_date"])
        df = df.groupby(["season", "fantasypros_id", "position"], as_index=False).tail(1)
    else:
        df = df.groupby(["season", "fantasypros_id", "position"], as_index=False).first()

    df["player_name"] = _first_present(df, ["player_name", "player"])
    if df["player_name"] is not None:
        df["player_name"] = df["player_name"].astype(str).str.strip()
    if "team" in df.columns:
        df["team"] = df["team"].astype(str).str.strip().str.upper()

    def _norm_pos(p: str) -> str | None:
        if p in (DST_POSITION, "K"):
            return p
        return normalize_fantasy_position(p)

    df["position"] = df["position"].apply(_norm_pos)
    df = df[df["position"].notna()].copy()
    return df.reset_index(drop=True)


def prepare_weekly_ecr(raw: pd.DataFrame) -> pd.DataFrame:
    """In-season weekly ECR rows."""
    df = filter_redraft_rows(raw)
    if df.empty:
        return df

    df["season"] = _parse_season(df)
    df["week"] = _parse_week(df)
    df = df[df["season"].notna() & df["week"].notna()].copy()
    df = df[df["week"] > 0].copy()
    df["season"] = df["season"].astype(int)
    df["week"] = df["week"].astype(int)

    df["ecr_rank"] = pd.to_numeric(df["ecr_rank"], errors="coerce")
    df = df[df["ecr_rank"].notna()].copy()
    df["ecr_rank"] = df["ecr_rank"].round().astype(int)

    if "scrape_date" in df.columns:
        df["scrape_date"] = pd.to_datetime(df["scrape_date"], errors="coerce").dt.date
        df = df.sort_values(
            ["season", "week", "fantasypros_id", "position", "scrape_date"]
        )
        df = df.groupby(
            ["season", "week", "fantasypros_id", "position"], as_index=False
        ).tail(1)

    df["player_name"] = _first_present(df, ["player_name", "player"])
    if df["player_name"] is not None:
        df["player_name"] = df["player_name"].astype(str).str.strip()
    if "team" in df.columns:
        df["team"] = df["team"].astype(str).str.strip().str.upper()

    def _norm_pos(p: str) -> str | None:
        if p in (DST_POSITION, "K"):
            return p
        return normalize_fantasy_position(p)

    df["position"] = df["position"].apply(_norm_pos)
    df = df[df["position"].notna()].copy()
    return df.reset_index(drop=True)


def entity_id_from_ranking_row(row: pd.Series) -> str | None:
    """Build canonical entity id before player-id mapping."""
    pos = str(row.get("position") or "").upper()
    if pos == DST_POSITION:
        team = str(row.get("team") or "").strip().upper()
        if team and re.match(r"^[A-Z]{2,4}$", team):
            return make_dst_entity_id(team)
        return None
    return None
