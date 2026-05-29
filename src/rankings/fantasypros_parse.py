"""Parse FantasyPros API JSON into normalized ranking / projection frames."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _merge_fp_player_row(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested ``player`` objects from consensus / projection payloads."""
    nested = row.get("player")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update({k: v for k, v in row.items() if k != "player"})
        return merged
    return row


def fp_player_display_name(row: dict[str, Any]) -> str | None:
    """Best display name from a FantasyPros player object."""
    row = _merge_fp_player_row(row)
    for key in ("player_name", "name", "player", "short_name", "full_name", "display_name"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    reverse = row.get("reverse_name")
    if reverse is not None and "," in str(reverse):
        last, first = [part.strip() for part in str(reverse).split(",", 1)]
        if first and last:
            return f"{first} {last}"
    return None


def _positions_list(row: dict[str, Any]) -> list[str]:
    raw = row.get("player_positions") or row.get("positions")
    if isinstance(raw, list):
        return [str(p).strip() for p in raw if str(p).strip()]
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        if "," in text:
            return [p.strip() for p in text.split(",") if p.strip()]
        return [text]
    return []


def _primary_position(sport_id: str, row: dict[str, Any]) -> str | None:
    """Best-effort position label for ECR row (matches stats table when possible)."""
    sid = str(sport_id).strip().lower()
    positions = _positions_list(row)
    if positions:
        pos = positions[0].upper()
    else:
        pos = str(
            row.get("player_position_id")
            or row.get("position_id")
            or row.get("position")
            or ""
        ).strip().upper()
        if "," in pos:
            pos = pos.split(",")[0].strip()
    if not pos or pos in ("ALL", "NAN"):
        return None

    if sid == "nba":
        from src.sports.nba.positions import normalize_nba_position

        return normalize_nba_position(pos) or pos
    if sid == "mlb":
        from src.sports.mlb.positions import normalize_mlb_field_position

        return normalize_mlb_field_position(pos) or pos
    if sid == "nhl":
        from src.sports.nhl.positions import normalize_nhl_skater_position
        from src.sports.nhl.positions import GOALIE_POSITION, is_goalie_position

        if is_goalie_position(pos):
            return GOALIE_POSITION
        return normalize_nhl_skater_position(pos) or pos
    return pos


def consensus_rankings_to_draft_ecr(
    payload: dict[str, Any],
    *,
    sport_id: str,
    season: int,
) -> pd.DataFrame:
    """``consensus-rankings`` response → draft ECR frame (pre-map)."""
    players = payload.get("players") or []
    if not isinstance(players, list):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for raw_p in players:
        if not isinstance(raw_p, dict):
            continue
        p = _merge_fp_player_row(raw_p)
        fpid = p.get("player_id")
        rank_raw = p.get("rank_ecr") or p.get("rank_ave") or p.get("ecr_avg")
        if rank_raw is None and isinstance(p.get("rank"), dict):
            rank_raw = p["rank"].get("ECR_AVG") or p["rank"].get("ECR")
        rank = _int_or_none(rank_raw)
        if fpid is None or rank is None or rank < 1:
            continue
        pos = _primary_position(sport_id, p)
        if not pos:
            continue
        rows.append(
            {
                "sport": sport_id,
                "fantasypros_id": str(fpid).strip(),
                "season": int(season),
                "position": pos,
                "ecr_rank": rank,
                "ecr_sd": _float_or_none(p.get("rank_std")),
                "player_name": fp_player_display_name(p),
                "team": str(p.get("player_team_id") or p.get("team_id") or "").strip().upper()
                or None,
                "scrape_date": date.today(),
            }
        )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.drop_duplicates(subset=["fantasypros_id", "season", "position"], keep="first")


def players_list_to_draft_ecr(
    payload: dict[str, Any],
    *,
    sport_id: str,
    season: int,
) -> pd.DataFrame:
    """
  ``/players`` snapshot with ``rank_ecr`` / ``rank_ave`` (MLB, NHL fallback).
    """
    players = payload.get("players") or []
    if not isinstance(players, list):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for raw_p in players:
        if not isinstance(raw_p, dict):
            continue
        p = _merge_fp_player_row(raw_p)
        fpid = p.get("player_id")
        rank = _int_or_none(p.get("rank_ecr") or p.get("rank_ave") or p.get("rank_adp"))
        # FP /players includes the full historical directory; rank_ecr=0 means unranked.
        if fpid is None or rank is None or rank < 1:
            continue
        pos = _primary_position(sport_id, p)
        if not pos:
            continue
        rows.append(
            {
                "sport": sport_id,
                "fantasypros_id": str(fpid).strip(),
                "season": int(season),
                "position": pos,
                "ecr_rank": rank,
                "ecr_sd": None,
                "player_name": fp_player_display_name(p),
                "team": str(p.get("team_id") or "").strip().upper() or None,
                "scrape_date": date.today(),
            }
        )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.drop_duplicates(subset=["fantasypros_id", "season", "position"], keep="first")


def projections_to_frame(
    payload: dict[str, Any],
    *,
    sport_id: str,
    season: int,
    projection_type: str,
    week: int = 0,
) -> pd.DataFrame:
    """Normalize ``/{sport}/{season}/projections`` payload."""
    players = payload.get("players") or payload.get("player") or []
    if not isinstance(players, list):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for raw_p in players:
        if not isinstance(raw_p, dict):
            continue
        p = _merge_fp_player_row(raw_p)
        fpid = p.get("fpid") or p.get("player_id")
        if fpid is None:
            continue
        stats = p.get("stats")
        if isinstance(stats, list) and stats:
            stats = stats[0] if isinstance(stats[0], dict) else {}
        if not isinstance(stats, dict):
            stats = {}
        pos = _primary_position(
            sport_id,
            {
                "player_position_id": p.get("position_id"),
                "player_positions": _positions_list(p) or ([p.get("position_id")] if p.get("position_id") else []),
            },
        )
        if not pos:
            pos = str(p.get("position_id") or "").strip().upper() or None
        projected_points = _float_or_none(
            p.get("points")
            or stats.get("points")
            or stats.get("points_ppr")
            or stats.get("fantasy_points")
        )
        rows.append(
            {
                "sport": sport_id,
                "fantasypros_id": str(fpid).strip(),
                "season": int(season),
                "week": int(week),
                "projection_type": str(projection_type).strip().lower(),
                "position": pos,
                "player_name": fp_player_display_name(p),
                "team": str(p.get("team_id") or p.get("player_team_id") or "").strip().upper()
                or None,
                "projected_points": projected_points,
                "stats_json": json.dumps(stats, default=str) if stats else None,
            }
        )

    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    dedupe = ["fantasypros_id", "season", "week", "projection_type", "position"]
    return out.drop_duplicates(subset=[c for c in dedupe if c in out.columns], keep="first")
