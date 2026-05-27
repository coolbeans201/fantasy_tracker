#!/usr/bin/env python3
"""Ingest NBA regular-season player stats via nba_api."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.connection import get_connection, init_schema  # noqa: E402
from src.sports.nba.player_positions import (  # noqa: E402
    fetch_season_positions,
    normalize_player_id,
)
from src.sports.nba.positions import normalize_nba_position  # noqa: E402
from src.sports.nba.scoring import compute_fp  # noqa: E402


def _season_str(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _col(raw: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in raw.columns:
            return raw[name]
    return pd.Series([None] * len(raw), index=raw.index)


def fetch_season(
    end_year: int, *, use_rosters: bool = True, refresh_positions: bool = False
) -> pd.DataFrame:
    from nba_api.stats.endpoints import leaguedashplayerstats

    season = _season_str(end_year)
    resp = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )
    time.sleep(0.6)
    raw = resp.get_data_frames()[0]
    if raw.empty:
        return pd.DataFrame()
    positions = fetch_season_positions(
        end_year,
        use_rosters=use_rosters,
        refresh_positions=refresh_positions,
    )
    out = pd.DataFrame()
    out["player_id"] = raw["PLAYER_ID"].map(normalize_player_id)
    out["player_name"] = raw["PLAYER_NAME"].astype(str)
    out["season"] = end_year
    out["position"] = out["player_id"].map(positions)
    if "PLAYER_POSITION" in raw.columns:
        missing = out["position"].isna()
        out.loc[missing, "position"] = _col(raw, "PLAYER_POSITION").loc[missing].apply(
            normalize_nba_position
        )
    missing = out["position"].isna()
    if missing.any():
        print(
            f"  WARNING: {int(missing.sum())} players missing position after position lookup"
        )
    # Keep unknown positions blank/null rather than guessing.
    out.loc[out["position"].isna(), "position"] = None
    out["team"] = _col(raw, "TEAM_ABBREVIATION").fillna("UNK").astype(str)
    games = pd.to_numeric(_col(raw, "GP"), errors="coerce").fillna(0).astype(int)
    out["games"] = games
    out["points"] = pd.to_numeric(_col(raw, "PTS"), errors="coerce").fillna(0) * games
    out["rebounds"] = pd.to_numeric(_col(raw, "REB"), errors="coerce").fillna(0) * games
    out["assists"] = pd.to_numeric(_col(raw, "AST"), errors="coerce").fillna(0) * games
    out["steals"] = pd.to_numeric(_col(raw, "STL"), errors="coerce").fillna(0) * games
    out["blocks"] = pd.to_numeric(_col(raw, "BLK"), errors="coerce").fillna(0) * games
    out["turnovers"] = pd.to_numeric(_col(raw, "TOV"), errors="coerce").fillna(0) * games
    out["three_pointers"] = pd.to_numeric(_col(raw, "FG3M"), errors="coerce").fillna(0) * games
    out["fantasy_points_espn"] = compute_fp(out)
    return out


def ingest_season(
    end_year: int, *, use_rosters: bool = True, refresh_positions: bool = False
) -> None:
    init_schema()
    conn = get_connection()
    frame = fetch_season(
        end_year, use_rosters=use_rosters, refresh_positions=refresh_positions
    )
    if frame.empty:
        print(f"No NBA data for season ending {end_year}.")
        conn.close()
        return
    conn.execute("DELETE FROM nba_player_season_stats WHERE season = ?", [end_year])
    conn.register("_nba", frame)
    conn.execute("INSERT INTO nba_player_season_stats SELECT * FROM _nba")
    conn.unregister("_nba")
    conn.execute("DELETE FROM nba_ingest_manifest WHERE season = ?", [end_year])
    conn.execute(
        """
        INSERT INTO nba_ingest_manifest (season, ingested_at, row_count)
        VALUES (?, ?, ?)
        """,
        [end_year, datetime.now(timezone.utc), len(frame)],
    )
    conn.close()
    print(f"Ingested NBA season {end_year}: {len(frame)} players")


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest NBA season stats into DuckDB")
    p.add_argument(
        "--season",
        type=int,
        help="Season end year (e.g. 2025 = 2024–25); not used with --bulk",
    )
    p.add_argument("--bulk", action="store_true", help="Ingest --from-year through --to-year")
    p.add_argument("--from-year", type=int, default=2000, help="First season end year (bulk)")
    p.add_argument("--to-year", type=int, default=2025, help="Last season end year (bulk)")
    p.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop bulk ingest on first error (default: skip and continue)",
    )
    p.add_argument(
        "--use-team-rosters",
        action="store_true",
        help="Deprecated: rosters are now used by default for more reliable positions.",
    )
    p.add_argument(
        "--index-only",
        action="store_true",
        help="Use PlayerIndex-only position lookup (faster first run, less accurate).",
    )
    p.add_argument(
        "--refresh-positions",
        action="store_true",
        help="Ignore disk cache and refetch NBA positions (writes data/cache/nba/).",
    )
    args = p.parse_args()
    if args.use_team_rosters and args.index_only:
        p.error("Choose only one of --index-only or --use-team-rosters")
    use_rosters = not args.index_only

    if args.bulk:
        years = range(args.from_year, args.to_year + 1)
        print(
            f"Bulk NBA ingest: {args.from_year}–{args.to_year} "
            f"({len(years)} seasons, end-year keys)"
        )
        skipped: list[int] = []
        for end_year in years:
            print(f"--- NBA {end_year} ({_season_str(end_year)}) ---")
            try:
                ingest_season(
                    end_year,
                    use_rosters=use_rosters,
                    refresh_positions=args.refresh_positions,
                )
            except Exception as exc:
                if args.fail_fast:
                    raise
                print(f"  WARNING: skipped NBA {end_year}: {exc}")
                skipped.append(end_year)
            time.sleep(1.0)
        if skipped:
            print(f"Skipped {len(skipped)} season(s): {skipped}")
            print("Re-run failed years, e.g. --season 2024")
    elif args.season is not None:
        ingest_season(
            args.season,
            use_rosters=use_rosters,
            refresh_positions=args.refresh_positions,
        )
    else:
        p.error("Provide --season YEAR or --bulk with --from-year and --to-year")


if __name__ == "__main__":
    main()
