#!/usr/bin/env python3
"""
Compare FantasyPros weekly ECR from consensus-rankings vs /rankings for one week.

Uses 2 API calls (counts against the ~100/day Public API limit). Run only when
validating which endpoint matches your expectations before switching ingest.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.rankings.fantasypros_client import (  # noqa: E402
    FantasyProsAPIError,
    consensus_rankings_path,
    get_json,
    rankings_path,
)
from src.rankings.fantasypros_config import get_fantasypros_api_key  # noqa: E402
from src.rankings.fantasypros_parse import (  # noqa: E402
    consensus_rankings_to_weekly_ecr,
    rankings_to_weekly_ecr,
)
from src.rankings.sport_ingest import (  # noqa: E402
    weekly_consensus_request_url,
    weekly_rankings_request_url,
)


def _top_ranks(frame, n: int = 12) -> list[tuple[str, str, int]]:
    if frame.empty:
        return []
    sort_col = "ecr_rank"
    sub = frame.sort_values(sort_col).head(n)
    out: list[tuple[str, str, int]] = []
    for _, row in sub.iterrows():
        out.append(
            (
                str(row.get("player_name") or ""),
                str(row.get("fantasypros_id") or ""),
                int(row["ecr_rank"]),
            )
        )
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sport", choices=["nba", "mlb", "nhl"], default="nba")
    p.add_argument("--season", type=int, default=2025)
    p.add_argument("--week", type=int, default=1)
    args = p.parse_args()

    try:
        key = get_fantasypros_api_key()
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)

    sid = args.sport
    season = args.season
    week = args.week
    print(f"Comparing weekly ECR for {sid.upper()} {season} week {week} (2 API calls)\n")

    consensus_url = weekly_consensus_request_url(sid, season, week)
    rankings_url = weekly_rankings_request_url(sid, season, week)
    print(f"  consensus: {consensus_url}")
    print(f"  rankings:  {rankings_url}\n")

    try:
        consensus_payload = get_json(
            consensus_rankings_path(sid, season),
            params={"position": "ALL", "week": week},
            api_key=key,
        )
        rankings_payload = get_json(
            rankings_path(sid, season),
            params={"week": week, "min": "true"},
            api_key=key,
        )
    except FantasyProsAPIError as exc:
        print(f"API error: {exc}")
        sys.exit(2)

    consensus_df = consensus_rankings_to_weekly_ecr(
        consensus_payload, sport_id=sid, season=season, week=week
    )
    rankings_df = rankings_to_weekly_ecr(
        rankings_payload, sport_id=sid, season=season, week=week
    )

    print(f"consensus-rankings: {len(consensus_df)} parsed rows")
    print(f"rankings:          {len(rankings_df)} parsed rows")

    if consensus_df.empty or rankings_df.empty:
        print("\nOne side is empty — check API response shape or week availability.")
        sys.exit(0)

    merged = consensus_df.merge(
        rankings_df,
        on=["fantasypros_id", "position"],
        how="inner",
        suffixes=("_consensus", "_rankings"),
    )
    print(f"matched (fp id + position): {len(merged)}")
    if not merged.empty:
        merged["rank_diff"] = merged["ecr_rank_consensus"] - merged["ecr_rank_rankings"]
        same = int((merged["rank_diff"] == 0).sum())
        print(f"exact same ecr_rank: {same}/{len(merged)}")
        if (merged["rank_diff"] != 0).any():
            worst = merged.reindex(
                merged["rank_diff"].abs().sort_values(ascending=False).index
            ).head(8)
            print("\nLargest rank gaps (consensus − rankings):")
            for _, row in worst.iterrows():
                print(
                    f"  {row['player_name_consensus']!r} {row['position']}: "
                    f"consensus={row['ecr_rank_consensus']} rankings={row['ecr_rank_rankings']} "
                    f"Δ={row['rank_diff']}"
                )

    print("\nTop 12 by consensus ECR:")
    for name, fpid, rank in _top_ranks(consensus_df):
        print(f"  {rank:>3}  {name} ({fpid})")
    print("\nTop 12 by rankings ECR:")
    for name, fpid, rank in _top_ranks(rankings_df):
        print(f"  {rank:>3}  {name} ({fpid})")

    experts = rankings_payload.get("experts")
    if isinstance(experts, dict):
        keys = sorted(str(k) for k in experts.keys())
        print(f"\nrankings payload expert/ranking keys ({len(keys)}): {keys[:20]}")
        if len(keys) > 20:
            print("  ...")


if __name__ == "__main__":
    main()
