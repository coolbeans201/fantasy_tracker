"""Resolve batting-row field position for season ingest."""

from __future__ import annotations

import pandas as pd

from src.sports.mlb.positions import DEFAULT_HITTER_POSITION, normalize_mlb_field_position


def resolve_batting_position(
    *,
    bref_pos: object,
    player_id: str,
    api_by_id: dict[str, str],
) -> str:
    """
    Position for a hitter season row.

    Priority: Baseball Reference ``Pos`` on the batting line (first token if
    multi-position, e.g. ``1B-DH`` → ``1B``), then MLB Stats API
    ``primaryPosition``, then ``DH`` only when both are missing.

    Few stored ``DH`` rows is normal: most hitters have a field position in BRef;
    ``DH`` is not “everyone who DH’d in games.”
    """
    pos = normalize_mlb_field_position(bref_pos)
    if pos:
        return pos
    api = api_by_id.get(str(player_id).strip())
    if api:
        return api
    return DEFAULT_HITTER_POSITION


def batting_positions_series(
    raw: pd.DataFrame,
    player_ids: pd.Series,
    *,
    api_by_id: dict[str, str],
) -> pd.Series:
    """Batting positions: BRef Pos column, then MLB API id map, then DH default."""
    pos_col = next(
        (name for name in ("Pos", "POS", "pos", "Position", "position") if name in raw.columns),
        None,
    )
    if pos_col is not None:
        from_bref = raw[pos_col].map(normalize_mlb_field_position)
    else:
        from_bref = pd.Series([pd.NA] * len(raw), index=raw.index)
    pid = player_ids.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    from_api = pid.map(api_by_id)
    return from_bref.fillna(from_api).fillna(DEFAULT_HITTER_POSITION).astype(str)
