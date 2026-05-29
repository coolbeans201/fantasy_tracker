"""Shared helpers for sport game-log ingest (parallel fetch, cache, bulk load)."""

from __future__ import annotations

import pickle
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.sports.game_logs import order_game_log_by_date

_CACHE_ROOT = Path(__file__).resolve().parents[2] / "data" / "cache" / "gamelogs"


def gamelog_cache_path(sport_id: str, season: int, player_id: str) -> Path:
    return _CACHE_ROOT / sport_id.strip().lower() / str(int(season)) / f"{player_id}.pkl"


def load_gamelog_cache(sport_id: str, season: int, player_id: str) -> pd.DataFrame | None:
    path = gamelog_cache_path(sport_id, season, player_id)
    if not path.is_file():
        return None
    try:
        with path.open("rb") as fh:
            frame = pickle.load(fh)
        return frame if isinstance(frame, pd.DataFrame) and not frame.empty else None
    except (OSError, pickle.PickleError, TypeError):
        return None


def save_gamelog_cache(sport_id: str, season: int, player_id: str, frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    path = gamelog_cache_path(sport_id, season, player_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        pickle.dump(frame, fh, protocol=pickle.HIGHEST_PROTOCOL)


def align_gamelog_columns(
    frame: pd.DataFrame,
    columns: tuple[str, ...] | list[str],
) -> pd.DataFrame:
    """Match a game-log frame to the DuckDB table column order (fills missing cols)."""
    if frame.empty:
        return frame
    out = frame.copy()
    out.columns = [str(c).lower() for c in out.columns]
    cols = [str(c).lower() for c in columns]
    for col in cols:
        if col not in out.columns:
            out[col] = None
    if "log_type" in cols:
        missing = out["log_type"].isna() | (out["log_type"].astype(str).str.strip() == "")
        if missing.any():
            default_log_type = "skater" if "saves" in cols else "hitting"
            out.loc[missing, "log_type"] = default_log_type
    return out[cols]


def _clean_gamelog_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    out["player_id"] = out["player_id"].astype(str).str.strip()
    out["game_id"] = out["game_id"].astype(str).str.strip()
    valid = (
        out["player_id"].ne("")
        & out["player_id"].str.lower().ne("nan")
        & out["player_id"].str.lower().ne("none")
        & out["player_id"].str.lower().ne("<na>")
        & out["game_id"].ne("")
        & out["game_id"].str.lower().ne("nan")
        & out["game_id"].str.lower().ne("none")
        & out["game_id"].str.lower().ne("<na>")
    )
    out = out[valid]
    if out.empty:
        return out
    subset = ["player_id", "season", "game_id"]
    if "log_type" in out.columns:
        subset.append("log_type")
    subset = [c for c in subset if c in out.columns]
    if len(subset) >= 3:
        out = out.drop_duplicates(subset=subset, keep="first")
    return order_game_log_by_date(out)


def _gamelog_cache_missing_box_scores(
    frame: pd.DataFrame,
    sport_id: str,
) -> bool:
    """True when a cached frame predates box-score columns (stats all null)."""
    if frame.empty:
        return False
    out = frame.copy()
    out.columns = [str(c).lower() for c in out.columns]
    sid = sport_id.strip().lower()
    if sid == "mlb":
        if "runs" not in out.columns and "innings_pitched" not in out.columns:
            return True
        hit_null = (
            "runs" in out.columns
            and out["runs"].isna().all()
            and out.get("home_runs", pd.Series(dtype=float)).isna().all()
        )
        pit_null = (
            "innings_pitched" in out.columns and out["innings_pitched"].isna().all()
        )
        log_types = (
            out["log_type"].astype(str).str.lower()
            if "log_type" in out.columns
            else pd.Series(["hitting"] * len(out), index=out.index)
        )
        has_hitting = log_types.eq("hitting").any()
        has_pitching = log_types.eq("pitching").any()
        if has_hitting and hit_null and (not has_pitching or pit_null):
            return True
    if sid == "nhl":
        log_types = (
            out["log_type"].astype(str).str.lower()
            if "log_type" in out.columns
            else pd.Series(["skater"] * len(out), index=out.index)
        )
        goalie_rows = out[log_types.eq("goalie")]
        if not goalie_rows.empty and "saves" in goalie_rows.columns:
            if goalie_rows["saves"].isna().all() or (
                pd.to_numeric(goalie_rows["saves"], errors="coerce").fillna(0) == 0
            ).all():
                if (
                    "goals_against" in goalie_rows.columns
                    and pd.to_numeric(goalie_rows["goals_against"], errors="coerce")
                    .fillna(0)
                    .gt(0)
                    .any()
                ):
                    return True
    return False


def fetch_players_parallel(
    tasks: list[dict[str, Any]],
    fetch_one: Callable[[dict[str, Any]], pd.DataFrame],
    *,
    sport_id: str,
    season: int,
    workers: int = 6,
    use_cache: bool = True,
    refresh_cache: bool = False,
    progress_every: int = 40,
    table_columns: tuple[str, ...] | list[str] | None = None,
) -> tuple[list[pd.DataFrame], int, int]:
    """
    Run per-player fetches with a thread pool.

    Returns ``(frames, loaded_player_count, failed_player_count)``.
    """
    if not tasks:
        return [], 0, 0

    workers = max(1, int(workers))
    sid = sport_id.strip().lower()
    year = int(season)
    frames: list[pd.DataFrame] = []
    loaded = 0
    failed = 0
    total = len(tasks)

    def _run(task: dict[str, Any]) -> tuple[str, pd.DataFrame | None, bool]:
        pid = str(task.get("player_id") or "").strip()
        if not pid:
            return pid, None, False
        if use_cache and not refresh_cache:
            cached = load_gamelog_cache(sid, year, pid)
            if cached is not None:
                if table_columns is not None:
                    cached = align_gamelog_columns(cached, table_columns)
                if _gamelog_cache_missing_box_scores(cached, sid):
                    cached = None
                else:
                    cached = _clean_gamelog_frame(cached)
                    if not cached.empty:
                        return pid, cached, True
        try:
            frame = fetch_one(task)
        except Exception:
            return pid, None, False
        frame = _clean_gamelog_frame(frame)
        if frame.empty:
            return pid, None, False
        if table_columns is not None:
            frame = align_gamelog_columns(frame, table_columns)
        if use_cache:
            save_gamelog_cache(sid, year, pid, frame)
        return pid, frame, False

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run, task): task for task in tasks}
        for fut in as_completed(futures):
            completed += 1
            pid, frame, _from_cache = fut.result()
            if frame is not None and not frame.empty:
                frames.append(frame)
                loaded += 1
            else:
                failed += 1
            if progress_every > 0 and (
                completed % progress_every == 0 or completed == total
            ):
                print(
                    f"  {sid.upper()} gamelog fetch: {completed}/{total} players "
                    f"({loaded} ok, {failed} missing)..."
                )
    return frames, loaded, failed


def bulk_replace_season_gamelogs(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    season: int,
    frames: list[pd.DataFrame],
    *,
    columns: tuple[str, ...] | list[str] | None = None,
) -> int:
    """Delete season rows and insert all game-log frames in one batch."""
    conn.execute(f"DELETE FROM {table} WHERE season = ?", [int(season)])
    if not frames:
        return 0
    frame = pd.concat(frames, ignore_index=True)
    frame = _clean_gamelog_frame(frame)
    if frame.empty:
        return 0
    if columns is not None:
        frame = align_gamelog_columns(frame, columns)
        cols_sql = ", ".join(columns)
        conn.register("_sport_gamelog_bulk", frame)
        conn.execute(
            f"INSERT INTO {table} ({cols_sql}) SELECT {cols_sql} FROM _sport_gamelog_bulk"
        )
    else:
        conn.register("_sport_gamelog_bulk", frame)
        conn.execute(f"INSERT INTO {table} SELECT * FROM _sport_gamelog_bulk")
    conn.unregister("_sport_gamelog_bulk")
    return len(frame)


def throttle_sleep(delay_sec: float) -> None:
    if delay_sec > 0:
        time.sleep(delay_sec)
