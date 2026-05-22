#!/usr/bin/env python3
"""Ingest completed NFL regular-season data into DuckDB."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import nflreadpy as nfl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import DATA_DIR, get_connection, init_schema  # noqa: E402
from src.db.maintenance import (  # noqa: E402
    recompute_games_played,
    rebuild_players_table,
    refresh_player_display_names,
)
from src.kicker_columns import KICKER_STAT_COLUMNS, NFLVERSE_KICKER_MAP  # noqa: E402
from src.positions import normalize_fantasy_position  # noqa: E402
from src.scoring.calc import apply_all_presets  # noqa: E402
from src.scoring.special import (  # noqa: E402
    DST_FP_COLUMN,
    KICKER_FP_COLUMN,
    apply_dst_points,
    apply_kicker_points,
)
from src.stats_columns import (  # noqa: E402
    FANTASY_POINT_COLUMNS,
    NFLVERSE_COL_MAP,
    STAT_COLUMNS,
    resolve_player_name,
)
from src.team_dst_columns import DST_STAT_COLUMNS, NFLVERSE_TEAM_DST_MAP  # noqa: E402


def _to_pandas(data) -> pd.DataFrame:
    if hasattr(data, "to_pandas"):
        return data.to_pandas()
    return pd.DataFrame(data)


def normalize_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Map nflverse weekly stats to our schema; keep all available stat fields."""
    out = pd.DataFrame()
    for src, dst in NFLVERSE_COL_MAP.items():
        if src in df.columns and dst not in out.columns:
            out[dst] = df[src]

    out["player_name"] = resolve_player_name(df)

    for col in [
        "player_id",
        "player_name",
        "season",
        "week",
        "season_type",
        "team",
        "position",
    ]:
        if col not in out.columns:
            out[col] = None

    for col in STAT_COLUMNS + KICKER_STAT_COLUMNS:
        if col not in out.columns:
            out[col] = 0
        else:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    for src, dst in NFLVERSE_KICKER_MAP.items():
        if src in df.columns:
            out[dst] = pd.to_numeric(df[src], errors="coerce").fillna(out.get(dst, 0))

    if "week" in out.columns:
        out["week"] = pd.to_numeric(out["week"], errors="coerce")

    # nflverse has no weekly games column; each REG row is one game played
    out["games"] = 1

    out = out[out["season_type"] == "REG"].copy()
    out["team"] = out["team"].fillna("UNK")
    if "opponent" in out.columns:
        out["opponent"] = out["opponent"].astype(str).str.strip()
        out.loc[
            out["opponent"].isin(("", "nan", "None", "NA", "<NA>")),
            "opponent",
        ] = pd.NA
    out["position"] = out["position"].apply(normalize_fantasy_position)

    before_skill = len(out)
    out = out[out["position"].notna()].copy()
    dropped_skill = before_skill - len(out)
    if dropped_skill:
        print(f"  Dropped {dropped_skill} weekly rows (not QB/RB/WR/TE/K)")

    # Older nflverse rows may lack player_id; coalesce from source frame if needed
    for alt_id in ("gsis_id", "nfl_id", "player_id"):
        if alt_id in df.columns:
            out["player_id"] = out["player_id"].fillna(df[alt_id])

    out["player_id"] = out["player_id"].astype(str).str.strip()
    out.loc[out["player_id"].isin(("", "nan", "None", "NA", "<NA>")), "player_id"] = pd.NA

    before = len(out)
    out = out[out["player_id"].notna()].copy()
    dropped = before - len(out)
    if dropped:
        print(f"  Dropped {dropped} weekly rows with missing player_id")

    return out


def _primary_position(positions: pd.Series) -> str | None:
    """Most common position label when weekly rows disagree (e.g. WR + KR)."""
    p = positions.dropna()
    if p.empty:
        return None
    modes = p.mode()
    return modes.iloc[0] if len(modes) else p.iloc[-1]


def build_aggregates(weekly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build season and season_team aggregates."""
    stat_cols = [c for c in STAT_COLUMNS + KICKER_STAT_COLUMNS if c in weekly.columns]
    fp_cols = [c for c in FANTASY_POINT_COLUMNS + [KICKER_FP_COLUMN] if c in weekly.columns]
    sum_agg = {c: (c, "sum") for c in stat_cols} | {c: (c, "sum") for c in fp_cols}

    # PK is (player_id, season, team) — do not split on position
    team = (
        weekly.groupby(["player_id", "season", "team"], as_index=False)
        .agg(
            player_name=("player_name", "first"),
            position=("position", _primary_position),
            games=("week", "nunique"),
            **sum_agg,
        )
    )

    # PK is (player_id, season) — one row per player per season
    season = (
        weekly.groupby(["player_id", "season"], as_index=False)
        .agg(
            player_name=("player_name", "first"),
            position=("position", _primary_position),
            teams=("team", lambda x: ", ".join(sorted(set(str(t) for t in x if pd.notna(t))))),
            games=("week", "nunique"),
            **sum_agg,
        )
    )

    best_rows = []
    for (pid, yr), group in weekly.groupby(["player_id", "season"]):
        pos = group["position"].iloc[0]
        fp_col = (
            KICKER_FP_COLUMN
            if pos == "K"
            else "fantasy_points_half_ppr"
        )
        if fp_col not in group.columns or group[fp_col].isna().all():
            continue
        idx = group[fp_col].idxmax()
        if pd.isna(idx):
            continue
        row = group.loc[idx]
        best_rows.append(
            {
                "player_id": pid,
                "season": yr,
                "best_week": row["week"],
                "best_week_fp": row[fp_col],
                "best_week_scoring": "kicker" if pos == "K" else "half_ppr",
            }
        )
    if best_rows:
        best = pd.DataFrame(best_rows)
        season = season.merge(best, on=["player_id", "season"], how="left")

    players = weekly.groupby("player_id", as_index=False).agg(
        player_name=("player_name", "last"),
        position=("position", _primary_position),
        last_season=("season", "max"),
    )

    return team, season, players


def normalize_team_dst(df: pd.DataFrame) -> pd.DataFrame:
    """Map nflverse team stats to D/ST schema (one row per team-week)."""
    out = pd.DataFrame()
    for src, dst in NFLVERSE_TEAM_DST_MAP.items():
        if src in df.columns and dst not in out.columns:
            out[dst] = df[src]

    for col in ["team", "season", "week", "season_type", "opponent", *DST_STAT_COLUMNS]:
        if col not in out.columns:
            out[col] = None if col in ("team", "season_type", "opponent") else 0
        elif col in DST_STAT_COLUMNS:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    if "week" in out.columns:
        out["week"] = pd.to_numeric(out["week"], errors="coerce")

    out["games"] = 1
    out = out[out["season_type"] == "REG"].copy()
    out["team"] = out["team"].fillna("UNK").astype(str).str.strip()
    if "opponent" in out.columns:
        out["opponent"] = out["opponent"].astype(str).str.strip()
        out.loc[
            out["opponent"].isin(("", "nan", "None", "NA", "<NA>")),
            "opponent",
        ] = pd.NA
    out = out[out["team"].notna() & (out["team"] != "")]
    return out


def build_team_dst_aggregates(weekly: pd.DataFrame) -> pd.DataFrame:
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


def _table_columns(table: str) -> list[str]:
    meta = {
        "weekly": [
            "player_id", "player_name", "season", "week", "season_type", "team", "opponent",
            "position", "games", *STAT_COLUMNS, *KICKER_STAT_COLUMNS, *FANTASY_POINT_COLUMNS,
            KICKER_FP_COLUMN,
        ],
        "season_team": [
            "player_id", "player_name", "season", "team", "position", "games",
            *STAT_COLUMNS, *KICKER_STAT_COLUMNS, *FANTASY_POINT_COLUMNS, KICKER_FP_COLUMN,
        ],
        "season": [
            "player_id", "player_name", "season", "position", "teams", "games",
            *STAT_COLUMNS, *KICKER_STAT_COLUMNS, *FANTASY_POINT_COLUMNS, KICKER_FP_COLUMN,
            "best_week", "best_week_fp", "best_week_scoring",
        ],
        "team_dst_weekly": [
            "team", "season", "week", "season_type", "opponent", "games",
            *DST_STAT_COLUMNS, DST_FP_COLUMN,
        ],
        "team_dst_season": [
            "team", "season", "games", *DST_STAT_COLUMNS, DST_FP_COLUMN,
            "best_week", "best_week_fp",
        ],
    }
    return meta[table]


def ingest_seasons(seasons: list[int], replace: bool = True) -> None:
    init_schema()
    conn = get_connection()

    raw = _to_pandas(nfl.load_player_stats(seasons))
    weekly = apply_kicker_points(apply_all_presets(normalize_weekly(raw)))

    raw_team = _to_pandas(nfl.load_team_stats(seasons))
    weekly_dst = apply_dst_points(normalize_team_dst(raw_team))
    season_dst = build_team_dst_aggregates(weekly_dst) if not weekly_dst.empty else pd.DataFrame()

    if weekly.empty and weekly_dst.empty:
        print("No regular-season rows found.")
        conn.close()
        return

    team, season_df, _players_df = build_aggregates(weekly) if not weekly.empty else (
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
    )

    def _insert(table: str, frame: pd.DataFrame, columns: list[str]) -> None:
        subset = frame.copy()
        for col in columns:
            if col not in subset.columns:
                subset[col] = pd.NA
        subset = subset[columns]
        if "player_id" in subset.columns:
            subset = subset[subset["player_id"].notna()].copy()
        pk_map = {
            "weekly_stats": ["player_id", "season", "week", "season_type", "team"],
            "season_team_stats": ["player_id", "season", "team"],
            "season_stats": ["player_id", "season"],
            "team_defense_weekly": ["team", "season", "week", "season_type"],
            "team_defense_season": ["team", "season"],
            "players": ["player_id"],
        }
        if table in pk_map:
            pk = [c for c in pk_map[table] if c in subset.columns]
            before = len(subset)
            subset = subset.drop_duplicates(subset=pk, keep="first")
            if len(subset) < before:
                print(f"  Deduped {before - len(subset)} duplicate rows for {table}")
        if subset.empty:
            return
        cols_sql = ", ".join(columns)
        conn.register("_ingest_tmp", subset)
        conn.execute(
            f"INSERT INTO {table} ({cols_sql}) SELECT {cols_sql} FROM _ingest_tmp"
        )
        conn.unregister("_ingest_tmp")

    for s in seasons:
        if replace:
            conn.execute("DELETE FROM weekly_stats WHERE season = ?", [s])
            conn.execute("DELETE FROM season_stats WHERE season = ?", [s])
            conn.execute("DELETE FROM season_team_stats WHERE season = ?", [s])
            conn.execute("DELETE FROM team_defense_weekly WHERE season = ?", [s])
            conn.execute("DELETE FROM team_defense_season WHERE season = ?", [s])
            conn.execute("DELETE FROM ingest_manifest WHERE season = ?", [s])

        w = weekly[weekly["season"] == s] if not weekly.empty else pd.DataFrame()
        t = team[team["season"] == s] if not team.empty else pd.DataFrame()
        ss = season_df[season_df["season"] == s] if not season_df.empty else pd.DataFrame()
        wd = weekly_dst[weekly_dst["season"] == s] if not weekly_dst.empty else pd.DataFrame()
        sd = season_dst[season_dst["season"] == s] if not season_dst.empty else pd.DataFrame()

        if not w.empty:
            _insert("weekly_stats", w, _table_columns("weekly"))
        if not t.empty:
            _insert("season_team_stats", t, _table_columns("season_team"))
        if not ss.empty:
            _insert("season_stats", ss, _table_columns("season"))
        if not wd.empty:
            _insert("team_defense_weekly", wd, _table_columns("team_dst_weekly"))
        if not sd.empty:
            _insert("team_defense_season", sd, _table_columns("team_dst_season"))

        row_count = len(w) + len(wd)
        conn.execute(
            """
            INSERT INTO ingest_manifest (season, ingested_at, row_count)
            VALUES (?, ?, ?)
            ON CONFLICT (season) DO UPDATE SET
                ingested_at = excluded.ingested_at,
                row_count = excluded.row_count
            """,
            [s, datetime.now(timezone.utc), row_count],
        )
        print(f"Ingested season {s}: {len(w)} player weekly, {len(wd)} team-DST weekly rows")

    recompute_games_played(conn)

    rebuild_players_table(conn)
    refresh_player_display_names(conn)

    conn.close()
    _write_manifest(seasons)


def _write_manifest(seasons: list[int]) -> None:
    manifest_path = DATA_DIR / "manifest.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    for s in seasons:
        existing[str(s)] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest NFL seasons into Fantasy Tracker")
    parser.add_argument("--season", type=int, action="append", help="Season year (repeatable)")
    parser.add_argument("--from-year", type=int, default=1999, help="Start year for bulk ingest")
    parser.add_argument("--to-year", type=int, default=2025, help="End year for bulk ingest (nflverse season year)")
    parser.add_argument("--bulk", action="store_true", help="Ingest all seasons in range")
    args = parser.parse_args()

    if args.bulk:
        seasons = list(range(args.from_year, args.to_year + 1))
        print(f"Bulk ingest: {seasons[0]}–{seasons[-1]} ({len(seasons)} seasons, one at a time)")
        for s in seasons:
            print(f"--- Season {s} ---")
            ingest_seasons([s])
    elif args.season:
        seasons = args.season
        print(f"Ingesting seasons: {seasons}")
        ingest_seasons(seasons)
    else:
        print("Ingesting seasons: [2023]")
        ingest_seasons([2023])


if __name__ == "__main__":
    main()
