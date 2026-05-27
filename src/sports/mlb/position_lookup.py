"""Load MLB field positions by player name (BRef standard page, FanGraphs fallback)."""

from __future__ import annotations

import re
import time
from io import StringIO

import pandas as pd

from src.sports.mlb.positions import normalize_mlb_field_position
from src.text_encoding import normalize_unicode_text


def _name_key(name: str) -> str:
    cleaned = normalize_unicode_text(name)
    cleaned = re.sub(r"[\*\#]+$", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.lower()


def _find_column(frame: pd.DataFrame, *candidates: str) -> str | None:
    lower = {str(c).lower(): c for c in frame.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    normalized = {k.replace("\xa0", " ").strip(): v for k, v in lower.items()}
    for cand in candidates:
        key = cand.lower().replace("\xa0", " ").strip()
        if key in normalized:
            return normalized[key]
    return None


def field_positions_from_bref_standard(year: int) -> dict[str, str]:
    """
    Scrape Baseball Reference standard batting page for Pos + Name.
    Returns map of normalized player name -> position (CF, 1B, …).
    """
    from pybaseball.datasources.bref import BRefSession

    url = f"https://www.baseball-reference.com/leagues/MLB/{year}-standard-batting.shtml"
    session = BRefSession()
    html = session.get(url).content.decode("utf-8", errors="replace")
    # BRef hides tables in HTML comments
    uncommented = re.sub(r"<!--|-->", "", html)
    try:
        try:
            tables = pd.read_html(StringIO(uncommented), flavor="lxml")
        except ImportError:
            tables = pd.read_html(StringIO(uncommented), flavor="html5lib")
    except (ValueError, ImportError):
        return {}

    mapping: dict[str, str] = {}
    for table in tables:
        if isinstance(table.columns, pd.MultiIndex):
            table.columns = [str(c[-1]) if isinstance(c, tuple) else str(c) for c in table.columns]
        name_col = _find_column(table, "Name", "Player", "name", "player")
        pos_col = _find_column(
            table,
            "Pos",
            "POS",
            "pos",
            "Pos Summary",
            "pos summary",
            "Position",
            "position",
        )
        if not name_col or not pos_col:
            continue
        for _, row in table.iterrows():
            name = str(row[name_col]).strip()
            if not name or name.lower() in ("name", "player"):
                continue
            pos = normalize_mlb_field_position(row[pos_col])
            if not pos:
                continue
            mapping[_name_key(name)] = pos
        if mapping:
            break
    return mapping


def field_positions_from_fangraphs(year: int) -> dict[str, str]:
    """FanGraphs season batting Pos column (when not blocked)."""
    try:
        from pybaseball import batting_stats
    except ImportError:
        return {}

    try:
        raw = batting_stats(year, qual=1)
    except Exception:
        return {}
    time.sleep(0.5)
    if raw is None or raw.empty:
        return {}

    pos_col = _find_column(raw, "Pos", "POS", "pos", "Position", "position")
    name_col = _find_column(raw, "Name", "Player", "player_name", "name")
    if not pos_col or not name_col:
        return {}

    mapping: dict[str, str] = {}
    for _, row in raw.iterrows():
        pos = normalize_mlb_field_position(row[pos_col])
        if not pos:
            continue
        mapping[_name_key(str(row[name_col]))] = pos
    return mapping


def load_field_position_map(year: int) -> dict[str, str]:
    """Best-effort name -> field position for a season."""
    by_name = field_positions_from_bref_standard(year)
    if len(by_name) < 50:
        fg = field_positions_from_fangraphs(year)
        by_name = {**fg, **by_name}
    return by_name


def resolve_field_position(
    player_name: str,
    pos_by_name: dict[str, str],
    *,
    default: str | None = None,
) -> str | None:
    return pos_by_name.get(_name_key(player_name), default)
