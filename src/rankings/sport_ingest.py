"""Draft ECR and projections ingest for MLB / NBA / NHL via FantasyPros API."""

from __future__ import annotations

import time
from typing import Any

import duckdb
import pandas as pd

from src.rankings.fantasypros_client import (
    FantasyProsAPIError,
    consensus_rankings_path,
    get_json,
    load_players_payload,
    projections_path,
)
from src.rankings.fantasypros_parse import (
    consensus_rankings_to_draft_ecr,
    players_list_to_draft_ecr,
    projections_to_frame,
)
from src.rankings.rankings_store import insert_ecr_draft, insert_fp_projections
from src.rankings.sport_map_players import (
    attach_sport_player_ids,
    fp_name_overlap_rate,
    fp_season_looks_mismatched,
    season_lookup_stats,
    sport_season_player_lookup,
)

_CONSENSUS_DRAFT_SPORTS = frozenset({"nba", "nfl", "mlb", "nhl"})
_PLAYERS_LIST_SPORTS = frozenset({"mlb", "nhl"})
_PROJECTION_SPORTS = frozenset({"nba", "mlb", "nfl"})

_NBA_CONSENSUS_POSITIONS = ("ALL", "PG", "SG", "SF", "PF", "C")
# Fewer calls than full position list — use ALL + hitter/pitcher buckets for rate limits.
_MLB_PROJECTION_POSITIONS = ("ALL", "H", "P")


def _consensus_positions(sport_id: str) -> tuple[str, ...]:
    if sport_id.strip().lower() == "nba":
        return _NBA_CONSENSUS_POSITIONS
    return ("ALL",)


def _fetch_draft_ecr_raw(
    sport_id: str,
    season: int,
    *,
    delay_sec: float = 0.35,
    refresh_fp_cache: bool = False,
) -> tuple[pd.DataFrame, str]:
    """Return unmapped draft ECR frame and source label."""
    sid = sport_id.strip().lower()
    year = int(season)

    if sid in _CONSENSUS_DRAFT_SPORTS:
        parts: list[pd.DataFrame] = []
        api_reported_season: str | int | None = None
        last_error: FantasyProsAPIError | None = None
        positions = _consensus_positions(sid)
        for pos in positions:
            try:
                payload = get_json(
                    consensus_rankings_path(sid, year),
                    params={"position": pos, "type": "draft"},
                )
            except FantasyProsAPIError as exc:
                last_error = exc
                continue
            if api_reported_season is None:
                api_reported_season = payload.get("season") or payload.get("year")
            chunk = consensus_rankings_to_draft_ecr(
                payload, sport_id=sid, season=year
            )
            if not chunk.empty:
                parts.append(chunk)
            if delay_sec > 0:
                time.sleep(delay_sec)
        if parts:
            out = pd.concat(parts, ignore_index=True)
            out = out.drop_duplicates(
                subset=["fantasypros_id", "season", "position"], keep="first"
            )
            out.attrs["fp_api_season"] = api_reported_season
            return out, "consensus-rankings"
        if last_error is not None and sid not in _PLAYERS_LIST_SPORTS:
            raise last_error

    if sid in _PLAYERS_LIST_SPORTS:
        payload, players_source = load_players_payload(
            sid, refresh=refresh_fp_cache
        )
        frame = players_list_to_draft_ecr(payload, sport_id=sid, season=year)
        if not frame.empty:
            return frame, players_source

    return pd.DataFrame(), "none"


def _fetch_projections_raw(
    sport_id: str,
    season: int,
    *,
    projection_type: str = "preseason",
    delay_sec: float = 0.35,
) -> pd.DataFrame:
    sid = sport_id.strip().lower()
    if sid not in _PROJECTION_SPORTS:
        return pd.DataFrame()

    year = int(season)
    week = 0
    parts: list[pd.DataFrame] = []

    if sid == "mlb":
        positions = _MLB_PROJECTION_POSITIONS
        params_base: dict[str, Any] = {"type": projection_type}
    elif sid == "nba":
        positions = ("ALL",)
        params_base = {"type": projection_type, "week": week}
    else:
        positions = ("ALL",)
        params_base = {"week": week, "positions": "QB:RB:WR:TE:K:DST"}

    for pos in positions:
        params = dict(params_base)
        if sid in ("mlb", "nba"):
            params["position"] = pos
        try:
            payload = get_json(projections_path(sid, year), params=params)
        except FantasyProsAPIError:
            continue
        chunk = projections_to_frame(
            payload,
            sport_id=sid,
            season=year,
            projection_type=projection_type,
            week=week,
        )
        if not chunk.empty:
            parts.append(chunk)
        if delay_sec > 0:
            time.sleep(delay_sec)

    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    dedupe = ["fantasypros_id", "season", "week", "projection_type", "position"]
    return out.drop_duplicates(subset=dedupe, keep="first")


def ingest_sport_draft_ecr(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
    *,
    replace: bool = True,
    delay_sec: float = 0.35,
    refresh_fp_cache: bool = False,
) -> dict[str, Any]:
    """Fetch draft ECR from FantasyPros, map to player_id, load ``ecr_draft``."""
    sid = sport_id.strip().lower()
    year = int(season)

    raw, source = _fetch_draft_ecr_raw(
        sid, year, delay_sec=delay_sec, refresh_fp_cache=refresh_fp_cache
    )
    if raw.empty:
        return {
            "sport": sid,
            "season": year,
            "status": "no_data",
            "source": source,
            "draft_rows": 0,
            "draft_unmapped": 0,
        }

    lookup = sport_season_player_lookup(conn, sid, year)
    lookup_stats = season_lookup_stats(lookup)
    fp_api_season = raw.attrs.get("fp_api_season")
    mismatch, overlap = fp_season_looks_mismatched(raw, lookup)
    if not mismatch and fp_api_season is not None:
        try:
            mismatch = int(fp_api_season) != year
        except (TypeError, ValueError):
            mismatch = str(fp_api_season).strip() != str(year)
    if overlap is None:
        overlap = fp_name_overlap_rate(raw, lookup) or 0.0

    if mismatch:
        sample = (
            raw.drop_duplicates(subset=["fantasypros_id"], keep="first")["player_name"]
            .dropna()
            .head(6)
            .tolist()
        )
        return {
            "sport": sid,
            "season": year,
            "status": "fp_season_mismatch",
            "source": source,
            "message": (
                f"FantasyPros data does not look like {sid.upper()} season {year} rankings. "
                f"The API returned names such as {sample[:3]!r} "
                f"(name overlap with your stats table: {overlap:.0%}). "
                "FantasyPros docs allow season>=2012 as a path parameter, but the payload "
                "may still be current-era rankings; historical ECR is not loaded."
            ),
            "fp_api_season": fp_api_season,
            "fp_name_overlap": overlap,
            "fp_sample_names": sample,
            "draft_rows": 0,
            "draft_unmapped": len(raw),
            "draft_unmapped_players": int(raw["fantasypros_id"].nunique())
            if "fantasypros_id" in raw.columns
            else len(raw),
            "raw_rows": len(raw),
            "stats_lookup_players": lookup_stats["lookup_players"],
            "stats_lookup_rows": lookup_stats["lookup_rows"],
        }

    mapped, unmapped = attach_sport_player_ids(raw, conn, sid, year)
    if replace:
        conn.execute(
            "DELETE FROM ecr_draft WHERE sport = ? AND season = ?",
            [sid, year],
        )

    inserted = insert_ecr_draft(conn, mapped)
    unmapped_players = 0
    if "fantasypros_id" in raw.columns:
        mapped_ids = (
            set(mapped["fantasypros_id"].astype(str)) if not mapped.empty else set()
        )
        unmapped_players = int(
            raw.loc[
                ~raw["fantasypros_id"].astype(str).isin(mapped_ids), "fantasypros_id"
            ].nunique()
        )
    return {
        "sport": sid,
        "season": year,
        "status": "ok",
        "source": source,
        "draft_rows": inserted,
        "draft_unmapped": unmapped,
        "draft_unmapped_players": unmapped_players,
        "raw_rows": len(raw),
        "stats_lookup_players": lookup_stats["lookup_players"],
        "stats_lookup_rows": lookup_stats["lookup_rows"],
    }


def ingest_sport_projections(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
    *,
    projection_type: str = "preseason",
    replace: bool = True,
    delay_sec: float = 0.35,
) -> dict[str, Any]:
    """Fetch preseason (or ROS) projections into ``fp_projections``."""
    sid = sport_id.strip().lower()
    year = int(season)

    if sid == "nhl":
        return {
            "sport": sid,
            "season": year,
            "status": "unsupported",
            "message": "FantasyPros API docs do not list NHL projections.",
            "projection_rows": 0,
        }

    raw = _fetch_projections_raw(
        sid, year, projection_type=projection_type, delay_sec=delay_sec
    )
    if raw.empty:
        return {
            "sport": sid,
            "season": year,
            "status": "no_data",
            "projection_rows": 0,
            "projection_unmapped": 0,
        }

    lookup = sport_season_player_lookup(conn, sid, year)
    lookup_stats = season_lookup_stats(lookup)
    mismatch, overlap = fp_season_looks_mismatched(raw, lookup)
    if overlap is None:
        overlap = fp_name_overlap_rate(raw, lookup) or 0.0
    if mismatch:
        sample = (
            raw.drop_duplicates(subset=["fantasypros_id"], keep="first")["player_name"]
            .dropna()
            .head(6)
            .tolist()
        )
        return {
            "sport": sid,
            "season": year,
            "status": "fp_season_mismatch",
            "projection_type": projection_type,
            "message": (
                f"FantasyPros projections do not match {sid.upper()} season {year} stats "
                f"(overlap {overlap:.0%}; sample names {sample[:3]!r}). Not loaded."
            ),
            "fp_name_overlap": overlap,
            "fp_sample_names": sample,
            "projection_rows": 0,
            "projection_unmapped": len(raw),
            "projection_unmapped_players": int(raw["fantasypros_id"].nunique())
            if "fantasypros_id" in raw.columns
            else len(raw),
            "raw_rows": len(raw),
            "stats_lookup_players": lookup_stats["lookup_players"],
            "stats_lookup_rows": lookup_stats["lookup_rows"],
        }

    mapped, unmapped = attach_sport_player_ids(raw, conn, sid, year)
    if replace:
        conn.execute(
            """
            DELETE FROM fp_projections
            WHERE sport = ? AND season = ? AND projection_type = ?
            """,
            [sid, year, projection_type],
        )

    inserted = insert_fp_projections(conn, mapped)
    unmapped_players = 0
    if "fantasypros_id" in raw.columns:
        mapped_ids = (
            set(mapped["fantasypros_id"].astype(str)) if not mapped.empty else set()
        )
        unmapped_players = int(
            raw.loc[
                ~raw["fantasypros_id"].astype(str).isin(mapped_ids), "fantasypros_id"
            ].nunique()
        )
    return {
        "sport": sid,
        "season": year,
        "status": "ok",
        "projection_type": projection_type,
        "projection_rows": inserted,
        "projection_unmapped": unmapped,
        "projection_unmapped_players": unmapped_players,
        "raw_rows": len(raw),
        "stats_lookup_players": lookup_stats["lookup_players"],
        "stats_lookup_rows": lookup_stats["lookup_rows"],
    }


def ingest_draft_ecr_stub(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
) -> dict:
    """Backward-compatible alias for ``ingest_sport_draft_ecr``."""
    return ingest_sport_draft_ecr(conn, sport_id, season)
