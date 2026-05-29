"""FantasyPros /players directory for NBA & MLB position overlay."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz, process

from src.rankings.fantasypros_client import (
    FantasyProsAPIError,
    load_players_payload,
)
from src.rankings.fantasypros_config import get_fantasypros_api_key
from src.text_encoding import normalize_unicode_text

_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "fantasypros"

_NBA_GENERIC = frozenset({"G", "GUARD", "F", "FORWARD", "GF", "FG", "FC", "CF"})
_MLB_COARSE_HITTER = frozenset({"H", "UTIL", "OF", ""})


def fantasypros_configured() -> bool:
    try:
        get_fantasypros_api_key()
        return True
    except RuntimeError:
        return False


def _cache_path(sport_id: str) -> Path:
    return _CACHE_DIR / f"{sport_id.strip().lower()}_players.json"


def _primary_position_from_fp_row(sport_id: str, row: dict[str, Any]) -> str | None:
    sid = sport_id.strip().lower()
    positions = row.get("positions")
    if isinstance(positions, list) and positions:
        raw = str(positions[0]).strip()
    else:
        raw = str(
            row.get("position_id")
            or row.get("primary_position")
            or row.get("yahoo_positions")
            or row.get("espn_positions")
            or ""
        ).strip()
        if "," in raw:
            raw = raw.split(",")[0].strip()

    if not raw:
        return None

    if sid == "nba":
        from src.sports.nba.positions import normalize_nba_position

        return normalize_nba_position(raw)
    if sid == "mlb":
        from src.sports.mlb.positions import is_pitcher_position, normalize_mlb_field_position

        norm = normalize_mlb_field_position(raw)
        if norm and not is_pitcher_position(norm):
            return norm
        return None
    return raw.upper()


def _players_payload_to_frame(sport_id: str, payload: dict[str, Any]) -> pd.DataFrame:
    players = payload.get("players") or []
    if not isinstance(players, list):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for p in players:
        if not isinstance(p, dict):
            continue
        pos = _primary_position_from_fp_row(sport_id, p)
        if not pos:
            continue
        name = normalize_unicode_text(p.get("player_name") or "")
        if not name:
            continue
        rows.append(
            {
                "fantasypros_id": str(p.get("player_id") or "").strip(),
                "player_name": name,
                "team": str(p.get("team_id") or "").strip().upper(),
                "position": pos,
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).drop_duplicates(subset=["player_name", "team"], keep="first")


def fetch_fp_players_frame(
    sport_id: str,
    *,
    refresh: bool = False,
    cache_hours: float = 12.0,
) -> pd.DataFrame:
    """Load FP player directory (cached under data/cache/fantasypros/)."""
    sid = sport_id.strip().lower()
    path = _cache_path(sid)
    if not refresh and path.is_file():
        age_h = (time.time() - path.stat().st_mtime) / 3600.0
        if age_h < cache_hours:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                frame = _players_payload_to_frame(sid, payload)
                if not frame.empty:
                    return frame
            except (OSError, json.JSONDecodeError):
                pass

    payload, _source = load_players_payload(sid, refresh=refresh)
    return _players_payload_to_frame(sid, payload)


def _match_fp_position(
    name: str,
    team: str,
    fp_df: pd.DataFrame,
    *,
    threshold: int = 88,
) -> str | None:
    if fp_df.empty or not name:
        return None
    team = str(team or "").strip().upper()
    pool = fp_df
    if team and team not in ("UNK", "NAN"):
        team_pool = fp_df[fp_df["team"].astype(str).str.upper() == team]
        if not team_pool.empty:
            pool = team_pool
    choices = pool["player_name"].astype(str).tolist()
    match = process.extractOne(
        normalize_unicode_text(name),
        choices,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=threshold,
    )
    if not match:
        return None
    return str(pool.loc[pool["player_name"] == match[0], "position"].iloc[0])


def _should_overlay_nba(current: str | None, fp_pos: str) -> bool:
    if not fp_pos:
        return False
    if current is None or (isinstance(current, float) and pd.isna(current)):
        return True
    cur = str(current).strip().upper()
    if not cur or cur in _NBA_GENERIC:
        return True
    # Prefer FP primary when it is the first listed skill position (e.g. PG not SG).
    return cur != fp_pos and cur in {"SG", "SF", "PF"} and fp_pos in {"PG", "C"}


def _should_overlay_mlb_hitter(current: str | None, fp_pos: str) -> bool:
    if not fp_pos:
        return False
    from src.sports.mlb.positions import is_pitcher_position

    if is_pitcher_position(fp_pos):
        return False
    if current is None or (isinstance(current, float) and pd.isna(current)):
        return True
    cur = str(current).strip().upper()
    if cur in _MLB_COARSE_HITTER:
        return True
    return cur != fp_pos and cur in {"UTIL", "OF"} and fp_pos in {
        "C",
        "1B",
        "2B",
        "3B",
        "SS",
        "LF",
        "CF",
        "RF",
        "DH",
    }


def _mlb_position_pk_key(
    row: pd.Series | dict[str, Any],
    *,
    position_override: str | None = None,
    team_override: str | None = None,
) -> tuple[Any, int, str, str]:
    """Primary-key tuple for mlb_player_season_stats (player_id, season, position, team)."""
    if isinstance(row, dict):
        get = row.get
    else:
        get = row.get
    pid = get("player_id")
    season = int(get("season"))
    team = str(
        team_override if team_override is not None else get("team") or ""
    ).strip().upper()
    pos = str(
        position_override if position_override is not None else get("position") or ""
    ).strip().upper()
    return (pid, season, pos, team)


def overlay_positions_on_frame(
    frame: pd.DataFrame,
    sport_id: str,
    *,
    refresh_fp_cache: bool = False,
) -> tuple[pd.DataFrame, int]:
    """
    Apply FantasyPros positions to a stats frame in-place copy.

    Returns (frame, number of rows updated).
    """
    if frame.empty or "player_name" not in frame.columns or "position" not in frame.columns:
        return frame, 0

    if not fantasypros_configured():
        return frame, 0

    sid = sport_id.strip().lower()
    if sid not in ("nba", "mlb"):
        return frame, 0

    try:
        fp_df = fetch_fp_players_frame(sid, refresh=refresh_fp_cache)
    except FantasyProsAPIError as exc:
        msg = str(exc)
        print(f"  FantasyPros positions skipped ({msg})")
        if "403" in msg:
            print(
                "  Tip: run scripts/fantasypros_probe.py — your key may not include "
                "NBA/MLB player data. Contact FantasyPros API support to enable it."
            )
        return frame, 0

    if fp_df.empty:
        print("  FantasyPros positions: empty player directory")
        return frame, 0

    out = frame.copy()
    updated = 0
    team_col = "team" if "team" in out.columns else None
    mlb_existing_keys: set[tuple[Any, ...]] | None = None
    mlb_assigned_keys: set[tuple[Any, ...]] | None = None
    if sid == "mlb" and team_col:
        mlb_existing_keys = set()
        mlb_assigned_keys = set()
        for _, r in out.iterrows():
            mlb_existing_keys.add(_mlb_position_pk_key(r))

    for idx, row in out.iterrows():
        name = str(row.get("player_name") or "").strip()
        team = str(row.get(team_col) or "") if team_col else ""
        fp_pos = _match_fp_position(name, team, fp_df)
        if not fp_pos:
            continue
        current = row.get("position")
        if sid == "nba":
            if not _should_overlay_nba(current, fp_pos):
                continue
        else:
            from src.sports.mlb.positions import is_pitcher_position

            if is_pitcher_position(current):
                continue
            if not _should_overlay_mlb_hitter(current, fp_pos):
                continue
            if mlb_existing_keys is not None and mlb_assigned_keys is not None:
                target_key = _mlb_position_pk_key(
                    row, position_override=fp_pos, team_override=team
                )
                if target_key in mlb_existing_keys and str(current).strip().upper() != fp_pos:
                    continue
                if target_key in mlb_assigned_keys:
                    continue
        if str(current).strip().upper() != fp_pos:
            out.at[idx, "position"] = fp_pos
            updated += 1
            if mlb_assigned_keys is not None:
                mlb_assigned_keys.add(
                    _mlb_position_pk_key(row, position_override=fp_pos, team_override=team)
                )

    return out, updated


def refresh_positions_in_database(
    conn,
    sport_id: str,
    *,
    season: int | None = None,
    refresh_fp_cache: bool = False,
) -> dict[str, int]:
    """Update stored season stats positions from FantasyPros directory."""
    from src.sports.player_seasons import stats_table

    table = stats_table(sport_id)
    sid = sport_id.strip().lower()
    if season is not None:
        df = conn.execute(
            f"""
            SELECT player_id, player_name, team, position, season
            FROM {table}
            WHERE season = ?
            """,
            [int(season)],
        ).df()
    else:
        df = conn.execute(
            f"""
            SELECT player_id, player_name, team, position, season
            FROM {table}
            """
        ).df()

    if df.empty:
        return {"rows": 0, "updated": 0}

    df.columns = [str(c).lower() for c in df.columns]
    original_positions = df["position"].copy()
    overlaid, _ = overlay_positions_on_frame(
        df, sid, refresh_fp_cache=refresh_fp_cache
    )
    changed_mask = (
        overlaid["position"].astype(str).str.strip().str.upper()
        != original_positions.astype(str).str.strip().str.upper()
    )
    if not changed_mask.any():
        return {"rows": len(df), "updated": 0}

    update_cols = ["player_id", "season", "position"]
    updates = overlaid.loc[changed_mask, update_cols].copy()
    updates["old_position"] = original_positions.loc[changed_mask].values
    if "team" in overlaid.columns:
        updates["team"] = overlaid.loc[changed_mask, "team"].values

    conn.register("_pos_updates", updates)
    if sid == "mlb":
        conn.execute(
            f"""
            UPDATE {table} AS t
            SET position = u.position
            FROM _pos_updates AS u
            WHERE t.player_id = u.player_id
              AND t.season = u.season
              AND COALESCE(upper(t.team), '') = COALESCE(upper(u.team), '')
              AND COALESCE(t.position, '') = COALESCE(u.old_position, '')
              AND t.position NOT IN ('SP', 'RP', 'P')
              AND u.position NOT IN ('SP', 'RP', 'P')
              AND NOT EXISTS (
                SELECT 1
                FROM {table} AS t2
                WHERE t2.player_id = t.player_id
                  AND t2.season = t.season
                  AND COALESCE(upper(t2.team), '') = COALESCE(upper(t.team), '')
                  AND t2.position = u.position
                  AND COALESCE(t2.position, '') IS DISTINCT FROM COALESCE(t.position, '')
              )
            """
        )
    else:
        conn.execute(
            f"""
            UPDATE {table} AS t
            SET position = u.position
            FROM _pos_updates AS u
            WHERE t.player_id = u.player_id
              AND t.season = u.season
              AND COALESCE(t.position, '') = COALESCE(u.old_position, '')
            """
        )
    conn.unregister("_pos_updates")
    return {"rows": len(df), "updated": int(changed_mask.sum())}
