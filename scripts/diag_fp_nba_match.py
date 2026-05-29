#!/usr/bin/env python3
"""Print why FP NBA rows fail to match season stats (sample)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "diag_fp_nba_match.txt"

import duckdb
from rapidfuzz import fuzz, process

from src.rankings.fantasypros_client import consensus_rankings_path, get_json, projections_path
from src.rankings.fantasypros_parse import (
    consensus_rankings_to_draft_ecr,
    fp_player_display_name,
    projections_to_frame,
)
from src.rankings.sport_map_players import (
    _fuzzy_match_player_id,
    fp_name_overlap_rate,
    fp_season_looks_mismatched,
    sport_season_player_lookup,
)
from src.text_encoding import normalize_unicode_text


def _sample_keys(payload: dict, n: int = 3) -> str:
    players = payload.get("players") or []
    lines = []
    for p in players[:n]:
        if isinstance(p, dict):
            lines.append(f"keys={sorted(p.keys())}")
            lines.append(f"  fp_name={fp_player_display_name(p)!r}")
            lines.append(f"  raw_name={p.get('player_name')!r} name={p.get('name')!r}")
    return "\n".join(lines)


def main() -> None:
    season = int(sys.argv[1]) if len(sys.argv) > 1 else 2012
    lines = [f"season={season}"]
    conn = duckdb.connect(str(ROOT / "data" / "fantasy_tracker.duckdb"))
    lookup = sport_season_player_lookup(conn, "nba", season)
    lines.append(f"lookup_players={lookup['player_id'].nunique() if not lookup.empty else 0}")

    try:
        payload = get_json(
            consensus_rankings_path("nba", season),
            params={"position": "ALL", "type": "draft"},
        )
        lines.append(
            f"fp_api_season={payload.get('season')!r} fp_api_year={payload.get('year')!r}"
        )
        lines.append("consensus_sample:")
        lines.append(_sample_keys(payload))
        raw = consensus_rankings_to_draft_ecr(payload, sport_id="nba", season=season)
        lines.append(f"consensus_parsed={len(raw)}")
        if not raw.empty:
            null_names = int(raw["player_name"].isna().sum() + (raw["player_name"] == "").sum())
            lines.append(f"consensus_null_names={null_names}")
            lines.append(f"consensus_name_sample={raw['player_name'].head(8).tolist()}")
            overlap = fp_name_overlap_rate(raw, lookup)
            mismatch, _ = fp_season_looks_mismatched(raw, lookup)
            lines.append(f"name_overlap={overlap!r} season_mismatch={mismatch}")
            stats_names = (
                lookup["player_name"].astype(str).map(normalize_unicode_text).tolist()
            )
            for _, row in raw.head(5).iterrows():
                name = normalize_unicode_text(str(row.get("player_name") or ""))
                best = process.extractOne(
                    name, stats_names, scorer=fuzz.token_sort_ratio
                )
                pid = _fuzzy_match_player_id(
                    name,
                    lookup,
                    position=str(row.get("position") or ""),
                    fuzzy_threshold=88,
                )
                lines.append(
                    f"  row name={name!r} team={row.get('team')!r} pos={row.get('position')!r} "
                    f"best={best} pid={pid}"
                )
    except Exception as exc:
        lines.append(f"consensus_error={exc!r}")

    try:
        pp = get_json(
            projections_path("nba", season),
            params={"type": "preseason", "week": 0},
        )
        lines.append(f"proj_api_season={pp.get('season')!r}")
        lines.append("projection_sample:")
        lines.append(_sample_keys(pp))
        proj = projections_to_frame(
            pp, sport_id="nba", season=season, projection_type="preseason"
        )
        lines.append(f"proj_parsed={len(proj)} null_names={int(proj['player_name'].isna().sum())}")
        if not proj.empty:
            lines.append(
                f"proj_overlap={fp_name_overlap_rate(proj, lookup)!r}"
            )
    except Exception as exc:
        lines.append(f"proj_error={exc!r}")

    conn.close()
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
