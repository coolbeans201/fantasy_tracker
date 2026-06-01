"""Draft ECR, weekly ECR, and projections ingest for MLB / NBA / NHL via FantasyPros API."""

from __future__ import annotations

import time
from typing import Any, Literal

import duckdb
import pandas as pd

from src.analytics.surprise import assign_positional_ecr_ranks, ecr_ranks_look_overall
from src.rankings.fantasypros_config import FP_PUBLIC_API_DAILY_CALL_LIMIT
from src.rankings.fantasypros_client import (
    FantasyProsAPIError,
    configure_fp_rate_limit,
    consensus_cache_path,
    consensus_rankings_path,
    get_json,
    load_players_payload,
    projections_path,
    rankings_cache_path,
    rankings_path,
    read_json_cache,
    write_json_cache,
)
from src.rankings.fantasypros_parse import (
    consensus_rankings_to_draft_ecr,
    consensus_rankings_to_weekly_ecr,
    players_list_to_draft_ecr,
    projections_to_frame,
    rankings_to_weekly_ecr,
)
from src.rankings.fantasypros_limits import FP_SPORT_DRAFT_ECR_MIN_SEASON, sport_draft_ecr_supported
from src.rankings.rankings_store import insert_ecr_draft, insert_ecr_weekly, insert_fp_projections
from src.rankings.mlb_ecr_positions import sync_mlb_pitcher_ecr_positions
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
_WEEKLY_ECR_SPORTS = frozenset({"nba", "mlb", "nhl", "nfl"})

# Used only with ``--positional-boards`` (multiplies API calls; default is ``ALL``).
_NBA_CONSENSUS_POSITIONS = ("PG", "SG", "SF", "PF", "C")
_MLB_CONSENSUS_POSITIONS = ("SP", "RP", "H")
_NHL_CONSENSUS_POSITIONS = ("C", "LW", "RW", "D", "G")
_MLB_PROJECTION_POSITIONS = ("ALL",)

_MAX_FP_WEEKS: dict[str, int] = {
    "nba": 26,
    "mlb": 27,
    "nhl": 26,
    "nfl": 18,
}

RankingType = Literal["draft", "weekly"]
WeeklyEcrSource = Literal["consensus", "rankings"]


def _consensus_positions(sport_id: str) -> tuple[str, ...]:
    sid = sport_id.strip().lower()
    if sid == "nba":
        return _NBA_CONSENSUS_POSITIONS
    if sid == "mlb":
        return _MLB_CONSENSUS_POSITIONS
    if sid == "nhl":
        return _NHL_CONSENSUS_POSITIONS
    return ("ALL",)


def max_fp_weeks(sport_id: str) -> int:
    return int(_MAX_FP_WEEKS.get(str(sport_id).strip().lower(), 26))


def _consensus_query_params(
    sport_id: str,
    *,
    position: str,
    ranking_type: RankingType,
    week: int | None = None,
) -> dict[str, Any]:
    """
    Query params for ``consensus-rankings`` (not ``compare-players``).

    The Public API docs use sport-specific ``type`` values (ROS, DRAFT, etc.) on
    this endpoint. ``ranking_type=weekly`` is only for *compare-players*.

    For MLB/NBA/NHL weekly boards, ``week`` alone selects the in-season board
    (see Public API example: draft = ``?position=ALL`` with default ``week=0``).
    """
    params: dict[str, Any] = {"position": position}
    sid = sport_id.strip().lower()

    if ranking_type == "weekly":
        if week is None:
            raise ValueError("week is required for weekly consensus")
        params["week"] = int(week)
        # NFL legacy docs mention Preseason/Weekly as type values; other sports use week.
        if sid == "nfl":
            params["type"] = "Weekly"
        return params

    # Draft / preseason: week 0 (explicit for clarity in caches and logs).
    params["week"] = 0
    if sid == "nfl":
        params["type"] = "draft"
    return params


def _consensus_query_string(
    sport_id: str,
    *,
    position: str,
    ranking_type: RankingType,
    week: int | None = None,
) -> str:
    from urllib.parse import urlencode

    return urlencode(_consensus_query_params(sport_id, position=position, ranking_type=ranking_type, week=week))


def weekly_consensus_request_url(
    sport_id: str,
    season: int,
    week: int,
    *,
    position: str = "ALL",
) -> str:
    """Exact Public API path + query for one weekly board (single GET)."""
    sid = sport_id.strip().lower()
    path = consensus_rankings_path(sid, int(season))
    qs = _consensus_query_string(
        sid, position=position, ranking_type="weekly", week=int(week)
    )
    return f"{path}?{qs}"


def weekly_rankings_request_url(sport_id: str, season: int, week: int) -> str:
    """``/{sport}/{season}/rankings?week=N`` — alternate weekly ECR source."""
    from urllib.parse import urlencode

    sid = sport_id.strip().lower()
    path = rankings_path(sid, int(season))
    return f"{path}?{urlencode({'week': int(week), 'min': 'true'})}"


def estimate_fp_api_calls(
    sport_id: str,
    *,
    draft: bool = False,
    weekly_weeks: list[int] | None = None,
    projections: bool = False,
    positional_boards: bool = False,
    refresh_players: bool = False,
    refresh_consensus_cache: bool = False,
) -> dict[str, Any]:
    """
    Upper bound on live HTTP calls for a planned ingest (cache hits = 0 calls).

    Defaults assume ``position=ALL`` (one consensus call per draft or per week).
    ``--positional-boards`` multiplies consensus calls (avoid on the 100/day tier).
    """
    sid = str(sport_id).strip().lower()
    positions_n = len(_consensus_positions(sid)) if positional_boards else 1
    calls = 0
    breakdown: list[str] = []

    if draft:
        n = positions_n
        if not refresh_consensus_cache:
            # Cached draft file still counts as 0 if present — caller may refine via plan.
            pass
        calls += n
        breakdown.append(f"draft consensus: {n} ({'per-position boards' if positional_boards else 'ALL'})")

    if weekly_weeks:
        n = len(weekly_weeks) * positions_n
        calls += n
        breakdown.append(
            f"weekly consensus: {n} ({len(weekly_weeks)} weeks × {positions_n} board(s))"
        )

    if projections and sid in _PROJECTION_SPORTS:
        proj_n = len(_MLB_PROJECTION_POSITIONS) if sid == "mlb" else 1
        calls += proj_n
        breakdown.append(f"projections: {proj_n} (ALL)")

    if refresh_players and sid in _PLAYERS_LIST_SPORTS:
        calls += 1
        breakdown.append("players list fallback: 1")

    return {
        "sport": sid,
        "estimated_calls": calls,
        "daily_limit": FP_PUBLIC_API_DAILY_CALL_LIMIT,
        "within_daily_limit": calls <= FP_PUBLIC_API_DAILY_CALL_LIMIT,
        "breakdown": breakdown,
    }


def print_fp_api_budget_warning(
    sport_id: str,
    *,
    draft: bool = False,
    weekly_weeks: list[int] | None = None,
    projections: bool = False,
    positional_boards: bool = False,
    refresh_players: bool = False,
) -> None:
    """Print planned API usage vs the Public API daily cap."""
    est = estimate_fp_api_calls(
        sport_id,
        draft=draft,
        weekly_weeks=weekly_weeks,
        projections=projections,
        positional_boards=positional_boards,
        refresh_players=refresh_players,
    )
    limit = est["daily_limit"]
    need = est["estimated_calls"]
    print(
        f"FantasyPros API budget: up to {need} live call(s) for this run "
        f"(Public API limit ≈ {limit}/day per key). "
        "Cached files under data/cache/fantasypros/ do not count."
    )
    for line in est["breakdown"]:
        print(f"  - {line}")
    if positional_boards:
        print(
            "  Warning: --positional-boards uses multiple calls per week/draft; "
            "prefer position=ALL (default) to stay under the daily cap."
        )
    if not est["within_daily_limit"]:
        print(
            f"  This plan exceeds {limit} calls — split across days "
            "(e.g. --weeks 1-10, then 11-20) or use --dry-run first."
        )


def plan_weekly_consensus_fetches(
    sport_id: str,
    season: int,
    weeks: list[int],
    *,
    positional_boards: bool = False,
    refresh_cache: bool = False,
) -> dict[str, Any]:
    """
    Summarize how many HTTP calls weekly ingest needs (no network).

    FantasyPros returns one week per request; there is no all-weeks endpoint.
    """
    sid = sport_id.strip().lower()
    positions = _consensus_positions(sid) if positional_boards else ("ALL",)
    planned: list[dict[str, Any]] = []
    cached = 0
    for week in weeks:
        for pos in positions:
            cache_path = consensus_cache_path(
                sid, int(season), position=pos, ranking_type="weekly", week=week
            )
            hit = cache_path.is_file() and not refresh_cache
            if hit:
                cached += 1
            planned.append(
                {
                    "week": week,
                    "position": pos,
                    "cache_path": str(cache_path),
                    "cached": hit,
                    "request": weekly_consensus_request_url(sid, season, week, position=pos),
                }
            )
    api_calls = len(planned) - cached
    return {
        "sport": sid,
        "season": int(season),
        "weeks": weeks,
        "positions_per_week": len(positions),
        "total_requests_if_no_cache": len(planned),
        "cached_skipped": cached,
        "api_calls_needed": api_calls,
        "requests": planned,
    }


def _parse_week_range(text: str, *, sport_id: str) -> list[int]:
    """Parse ``1-26`` or ``1,3,5`` into week numbers."""
    cap = max_fp_weeks(sport_id)
    weeks: set[int] = set()
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo_s, hi_s = part.split("-", 1)
            lo, hi = int(lo_s.strip()), int(hi_s.strip())
            if lo > hi:
                lo, hi = hi, lo
            for w in range(lo, hi + 1):
                if 1 <= w <= cap:
                    weeks.add(w)
        else:
            w = int(part)
            if 1 <= w <= cap:
                weeks.add(w)
    return sorted(weeks)


def _load_consensus_payload(
    sport_id: str,
    season: int,
    *,
    position: str,
    ranking_type: RankingType,
    week: int | None = None,
    use_cache: bool = True,
    refresh_cache: bool = False,
    allow_stale_on_rate_limit: bool = True,
) -> tuple[dict[str, Any] | None, str]:
    """
    Load consensus JSON from disk cache or API.

    Returns ``(payload, source)`` where source is ``cache``, ``api``, or
    ``cache-stale`` (used after 429).
    """
    sid = sport_id.strip().lower()
    year = int(season)
    params = _consensus_query_params(
        sid, position=position, ranking_type=ranking_type, week=week
    )

    cache_path = consensus_cache_path(
        sid, year, position=position, ranking_type=ranking_type, week=week
    )
    if use_cache and not refresh_cache:
        cached = read_json_cache(cache_path)
        if cached is not None:
            return cached, "cache"

    try:
        # One GET per week; fail fast on 429 so re-run can resume from cache.
        payload = get_json(
            consensus_rankings_path(sid, year),
            params=params,
            max_retries=2,
            try_auth_fallback=False,
        )
        write_json_cache(cache_path, payload)
        return payload, "api"
    except FantasyProsAPIError as exc:
        if allow_stale_on_rate_limit and "429" in str(exc):
            stale = read_json_cache(cache_path)
            if stale is not None:
                print(
                    f"  FantasyPros 429 for {sid.upper()} {position} {ranking_type}"
                    f"{f' w{week}' if week else ''}; using cached response."
                )
                return stale, "cache-stale"
        raise


def _load_rankings_payload(
    sport_id: str,
    season: int,
    *,
    week: int,
    use_cache: bool = True,
    refresh_cache: bool = False,
    allow_stale_on_rate_limit: bool = True,
) -> tuple[dict[str, Any] | None, str]:
    """Load ``/{sport}/{season}/rankings`` for one week (cache or API)."""
    sid = sport_id.strip().lower()
    year = int(season)
    fp_week = int(week)
    params = {"week": fp_week, "min": "true"}
    cache_path = rankings_cache_path(sid, year, week=fp_week)
    if use_cache and not refresh_cache:
        cached = read_json_cache(cache_path)
        if cached is not None:
            return cached, "cache"

    try:
        payload = get_json(
            rankings_path(sid, year),
            params=params,
            max_retries=2,
            try_auth_fallback=False,
        )
        write_json_cache(cache_path, payload)
        return payload, "api"
    except FantasyProsAPIError as exc:
        if allow_stale_on_rate_limit and "429" in str(exc):
            stale = read_json_cache(cache_path)
            if stale is not None:
                print(
                    f"  FantasyPros 429 for {sid.upper()} rankings w{fp_week}; "
                    "using cached response."
                )
                return stale, "cache-stale"
        raise


def _payload_to_ecr_frame(
    payload: dict[str, Any],
    *,
    sport_id: str,
    season: int,
    ranking_type: RankingType,
    position: str,
    week: int | None = None,
    weekly_source: WeeklyEcrSource = "consensus",
) -> pd.DataFrame:
    sid = sport_id.strip().lower()
    bucket = position if sid in ("mlb", "nba") and position != "ALL" else None
    if ranking_type == "weekly":
        if week is None:
            return pd.DataFrame()
        if weekly_source == "rankings":
            return rankings_to_weekly_ecr(
                payload,
                sport_id=sid,
                season=season,
                week=int(week),
                position_bucket=bucket,
            )
        return consensus_rankings_to_weekly_ecr(
            payload,
            sport_id=sid,
            season=season,
            week=int(week),
            position_bucket=bucket,
        )
    return consensus_rankings_to_draft_ecr(
        payload,
        sport_id=sid,
        season=season,
        position_bucket=bucket,
    )


def _normalize_positional_ecr(frame: pd.DataFrame, *, used_all_board: bool) -> pd.DataFrame:
    if frame.empty:
        return frame
    if used_all_board or ecr_ranks_look_overall(frame):
        return assign_positional_ecr_ranks(frame)
    return frame


def _fetch_consensus_ecr_raw(
    sport_id: str,
    season: int,
    *,
    ranking_type: RankingType = "draft",
    week: int | None = None,
    weeks: list[int] | None = None,
    positional_boards: bool = False,
    weekly_source: WeeklyEcrSource = "consensus",
    delay_sec: float = 0.35,
    use_cache: bool = True,
    refresh_cache: bool = False,
) -> tuple[pd.DataFrame, str]:
    """
    Fetch consensus rankings (default ``position=ALL`` + in-code positional reorder).

    For weekly ingest, pass ``weeks=[1,2,...]`` or a single ``week``.

    ``delay_sec`` is the minimum gap between live API calls (cache hits do not wait).
    """
    sid = sport_id.strip().lower()
    year = int(season)
    configure_fp_rate_limit(
        min_interval_sec=max(delay_sec, 5.0 if ranking_type == "weekly" else 2.0)
    )
    if ranking_type == "weekly":
        week_list = weeks if weeks is not None else ([int(week)] if week is not None else [])
        if not week_list:
            week_list = list(range(1, max_fp_weeks(sid) + 1))
    else:
        week_list = [None]  # type: ignore[list-item]

    if ranking_type == "weekly" and weekly_source == "rankings":
        positions = ("ALL",)
    else:
        positions = _consensus_positions(sid) if positional_boards else ("ALL",)
    parts: list[pd.DataFrame] = []
    api_reported_season: str | int | None = None
    last_error: FantasyProsAPIError | None = None

    total_steps = len(week_list) * len(positions)
    step = 0
    for fp_week in week_list:
        for pos in positions:
            step += 1
            label = f"{sid.upper()} {ranking_type}"
            if ranking_type == "weekly" and weekly_source == "rankings":
                label += " (rankings)"
            if fp_week is not None:
                label += f" w{fp_week}"
            try:
                if ranking_type == "weekly" and weekly_source == "rankings":
                    if fp_week is None:
                        continue
                    payload, source = _load_rankings_payload(
                        sid,
                        year,
                        week=int(fp_week),
                        use_cache=use_cache,
                        refresh_cache=refresh_cache,
                    )
                else:
                    payload, source = _load_consensus_payload(
                        sid,
                        year,
                        position=pos,
                        ranking_type=ranking_type,
                        week=fp_week,
                        use_cache=use_cache,
                        refresh_cache=refresh_cache,
                    )
            except FantasyProsAPIError as exc:
                last_error = exc
                print(f"  [{step}/{total_steps}] {label}: failed ({exc})")
                continue
            if payload is None:
                continue
            if source == "api":
                print(f"  [{step}/{total_steps}] {label}: API")
                if delay_sec > 0:
                    time.sleep(delay_sec)
            elif source == "cache-stale":
                print(f"  [{step}/{total_steps}] {label}: cache (429 fallback)")
            else:
                print(f"  [{step}/{total_steps}] {label}: cache")
            if api_reported_season is None:
                api_reported_season = payload.get("season") or payload.get("year")
            chunk = _payload_to_ecr_frame(
                payload,
                sport_id=sid,
                season=year,
                ranking_type=ranking_type,
                position=pos,
                week=fp_week,
                weekly_source=weekly_source,
            )
            if not chunk.empty:
                chunk = _normalize_positional_ecr(chunk, used_all_board=(pos == "ALL"))
                parts.append(chunk)

    if parts:
        out = pd.concat(parts, ignore_index=True)
        dedupe = ["fantasypros_id", "season", "position"]
        if ranking_type == "weekly":
            dedupe = ["fantasypros_id", "season", "week", "position"]
        out = out.drop_duplicates(subset=dedupe, keep="first")
        out.attrs["fp_api_season"] = api_reported_season
        if ranking_type == "weekly" and weekly_source == "rankings":
            label = "rankings-weekly"
        elif ranking_type == "weekly":
            label = "consensus-rankings-weekly"
        else:
            label = "consensus-rankings"
        return out, label
    if last_error is not None and sid not in _PLAYERS_LIST_SPORTS:
        raise last_error
    return pd.DataFrame(), "none"


def _fetch_draft_ecr_raw(
    sport_id: str,
    season: int,
    *,
    delay_sec: float = 0.35,
    refresh_fp_cache: bool = False,
    positional_boards: bool = False,
    use_cache: bool = True,
    refresh_consensus_cache: bool = False,
) -> tuple[pd.DataFrame, str]:
    """Return unmapped draft ECR frame and source label."""
    sid = sport_id.strip().lower()
    year = int(season)

    if sid in _CONSENSUS_DRAFT_SPORTS:
        frame, source = _fetch_consensus_ecr_raw(
            sid,
            year,
            ranking_type="draft",
            positional_boards=positional_boards,
            delay_sec=delay_sec,
            use_cache=use_cache,
            refresh_cache=refresh_consensus_cache,
        )
        if not frame.empty:
            return frame, source

    if sid in _PLAYERS_LIST_SPORTS:
        payload, players_source = load_players_payload(
            sid, refresh=refresh_fp_cache or refresh_consensus_cache
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
    positional_boards: bool = False,
    use_cache: bool = True,
    refresh_consensus_cache: bool = False,
) -> dict[str, Any]:
    """Fetch draft ECR from FantasyPros, map to player_id, load ``ecr_draft``."""
    sid = sport_id.strip().lower()
    year = int(season)

    if not sport_draft_ecr_supported(sid, year):
        return {
            "sport": sid,
            "season": year,
            "status": "unsupported_season",
            "message": (
                f"FantasyPros draft ECR is not supported for {sid.upper()} before "
                f"{FP_SPORT_DRAFT_ECR_MIN_SEASON}. The API may accept older season "
                "parameters but returns current-era rankings, not historical boards."
            ),
            "draft_rows": 0,
            "draft_unmapped": 0,
        }

    print_fp_api_budget_warning(
        sid,
        draft=True,
        positional_boards=positional_boards,
        refresh_players=refresh_fp_cache,
    )

    raw, source = _fetch_draft_ecr_raw(
        sid,
        year,
        delay_sec=delay_sec,
        refresh_fp_cache=refresh_fp_cache,
        positional_boards=positional_boards,
        use_cache=use_cache,
        refresh_consensus_cache=refresh_consensus_cache,
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
    if sid == "mlb" and not mapped.empty:
        mapped, _ = sync_mlb_pitcher_ecr_positions(mapped, conn, year)
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


def ingest_sport_weekly_ecr(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
    *,
    weeks: list[int] | None = None,
    replace: bool = True,
    delay_sec: float = 0.35,
    positional_boards: bool = False,
    weekly_source: WeeklyEcrSource = "consensus",
    use_cache: bool = True,
    refresh_consensus_cache: bool = False,
) -> dict[str, Any]:
    """Fetch weekly ECR into ``ecr_weekly`` (default: consensus ``position=ALL`` per week)."""
    sid = sport_id.strip().lower()
    if sid not in _WEEKLY_ECR_SPORTS:
        return {
            "sport": sid,
            "season": int(season),
            "status": "unsupported",
            "weekly_rows": 0,
        }
    year = int(season)
    week_list = weeks if weeks is not None else list(range(1, max_fp_weeks(sid) + 1))

    print_fp_api_budget_warning(
        sid,
        weekly_weeks=week_list,
        positional_boards=positional_boards,
    )

    plan = plan_weekly_consensus_fetches(
        sid,
        year,
        week_list,
        positional_boards=positional_boards,
        refresh_cache=refresh_consensus_cache,
    )
    if weekly_source == "rankings":
        print(
            f"Weekly ECR (rankings endpoint): {len(week_list)} API GET(s) needed "
            f"({plan['cached_skipped']} cached from consensus plan). "
            f"Each week: {weekly_rankings_request_url(sid, year, week_list[0] if week_list else 1)}"
        )
    else:
        print(
            f"Weekly ECR: {plan['api_calls_needed']} API GET(s) needed "
            f"({plan['cached_skipped']} cached). "
            "Each week is one call: "
            f".../consensus-rankings?position=ALL&week=N (no type=weekly; week selects the board)"
        )

    raw, source = _fetch_consensus_ecr_raw(
        sid,
        year,
        ranking_type="weekly",
        weeks=week_list,
        positional_boards=positional_boards,
        weekly_source=weekly_source,
        delay_sec=delay_sec,
        use_cache=use_cache,
        refresh_cache=refresh_consensus_cache,
    )
    if raw.empty:
        return {
            "sport": sid,
            "season": year,
            "status": "no_data",
            "source": source,
            "weekly_rows": 0,
            "weekly_unmapped": 0,
        }

    lookup = sport_season_player_lookup(conn, sid, year)
    lookup_stats = season_lookup_stats(lookup)
    mapped, unmapped = attach_sport_player_ids(raw, conn, sid, year)
    if sid == "mlb" and not mapped.empty:
        mapped, _ = sync_mlb_pitcher_ecr_positions(mapped, conn, year)

    if replace:
        if week_list:
            placeholders = ",".join("?" * len(week_list))
            conn.execute(
                f"""
                DELETE FROM ecr_weekly
                WHERE sport = ? AND season = ? AND week IN ({placeholders})
                """,
                [sid, year, *week_list],
            )
        else:
            conn.execute(
                "DELETE FROM ecr_weekly WHERE sport = ? AND season = ?",
                [sid, year],
            )

    inserted = insert_ecr_weekly(conn, mapped)
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
        "weekly_rows": inserted,
        "weekly_unmapped": unmapped,
        "weekly_unmapped_players": unmapped_players,
        "raw_rows": len(raw),
        "weeks_requested": week_list,
        "cache_dir": str(cache_dir),
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
