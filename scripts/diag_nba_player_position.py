#!/usr/bin/env python3
"""Print NBA stats API URLs and raw position labels for one player (default: Anthony Davis)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sports.nba.player_positions import (  # noqa: E402
    _positions_from_player_index,
    _positions_from_team_rosters,
    fetch_season_positions,
    normalize_player_id,
)
from src.sports.nba.positions import normalize_nba_position  # noqa: E402

DEFAULT_PLAYER_ID = "203076"  # Anthony Davis
LAKERS_TEAM_ID = 1610612747


def _season_str(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _print_url(label: str, endpoint) -> None:
    url = endpoint.get_request_url() if hasattr(endpoint, "get_request_url") else "(no URL)"
    print(f"\n=== {label} ===")
    print(url)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--season", type=int, default=2025, help="Season end year (e.g. 2025 = 2024-25)")
    p.add_argument("--player-id", default=DEFAULT_PLAYER_ID, help="NBA PLAYER_ID / PERSON_ID")
    p.add_argument("--team-id", type=int, default=LAKERS_TEAM_ID, help="Team for roster lookup")
    args = p.parse_args()

    pid = normalize_player_id(args.player_id)
    season = _season_str(args.season)

    from nba_api.stats.endpoints import (
        commonteamroster,
        leaguedashplayerstats,
        leaguedashteamstats,
        playerindex,
    )

    print(f"Player ID: {pid}  |  Season: {season}")

    # 1) Season stats (ingest uses this for counting stats; optional PLAYER_POSITION column)
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )
    _print_url("LeagueDashPlayerStats (season ingest)", stats)
    time.sleep(0.6)
    sdf = stats.get_data_frames()[0]
    srow = sdf[sdf["PLAYER_ID"].astype(str).map(normalize_player_id) == pid]
    if srow.empty:
        print("Not found in LeagueDashPlayerStats.")
    else:
        name = srow.iloc[0].get("PLAYER_NAME")
        pos_cols = [c for c in srow.columns if "POS" in c.upper()]
        print(f"PLAYER_NAME: {name}")
        for c in pos_cols:
            raw = srow.iloc[0][c]
            print(f"  {c}: {raw!r} -> normalize: {normalize_nba_position(raw)!r}")

    # 2) PlayerIndex (position lookup pass 1)
    pi = playerindex.PlayerIndex(season=season, league_id="00")
    _print_url("PlayerIndex (position lookup)", pi)
    time.sleep(0.6)
    idx = pi.get_data_frames()[0]
    id_col = "PERSON_ID" if "PERSON_ID" in idx.columns else "PLAYER_ID"
    irow = idx[idx[id_col].astype(str).map(normalize_player_id) == pid]
    if irow.empty:
        print("Not found in PlayerIndex.")
    else:
        raw = irow.iloc[0].get("POSITION")
        print(f"POSITION: {raw!r} -> normalize: {normalize_nba_position(raw)!r}")

    # 3) LeagueDashTeamStats (lists teams before roster loop)
    teams = leaguedashteamstats.LeagueDashTeamStats(
        season=season,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    )
    _print_url("LeagueDashTeamStats (team list for roster loop)", teams)
    time.sleep(0.6)

    # 4) CommonTeamRoster (position lookup pass 2 — overwrites PlayerIndex when specific)
    roster = commonteamroster.CommonTeamRoster(team_id=int(args.team_id), season=season)
    _print_url(f"CommonTeamRoster (team_id={args.team_id})", roster)
    time.sleep(0.6)
    rdf = roster.get_data_frames()[0]
    rrow = rdf[rdf["PLAYER_ID"].astype(str).map(normalize_player_id) == pid]
    if rrow.empty:
        print(f"Not on team_id={args.team_id} roster for {season}.")
    else:
        raw = rrow.iloc[0]["POSITION"]
        skipped = str(raw).strip().upper().replace(" ", "") in {
            "G",
            "GUARD",
            "GF",
            "FG",
            "CF",
        }
        print(f"PLAYER: {rrow.iloc[0].get('PLAYER')}")
        print(f"POSITION: {raw!r} -> normalize: {normalize_nba_position(raw)!r}")
        if skipped:
            print(
                "  (roster ingest SKIPS unresolved coarse guard labels — "
                "falls back to PlayerIndex / LeagueDash / FantasyPros)"
            )

    # 5) What our merge produces (same as ingest)
    print("\n=== fetch_season_positions() merge (ingest) ===")
    index_map = _positions_from_player_index(season)
    roster_map = _positions_from_team_rosters(season)
    merged = dict(index_map)
    merged.update(roster_map)
    print(f"PlayerIndex only: {index_map.get(pid)!r}")
    print(f"Roster only:      {roster_map.get(pid)!r}")
    print(f"Final (roster wins): {merged.get(pid)!r}")
    full = fetch_season_positions(args.season, refresh_positions=True)
    print(f"Cached fetch_season_positions({args.season}): {full.get(pid)!r}")


if __name__ == "__main__":
    main()
