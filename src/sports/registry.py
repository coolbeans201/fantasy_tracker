"""Sport metadata and plugin dispatch."""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

from src.settings import get_min_games_default
from src.sports.window_leaders import aggregate_leader_window

DEFAULT_SPORT = "nfl"

SPORT_IDS = ("nfl", "mlb", "nba", "nhl")


@dataclass(frozen=True)
class SportMeta:
    sport_id: str
    label: str
    icon: str
    game_unit: str  # week | game
    season_label_hint: str
    ingest_command: str
    data_source: str
    license_note: str
    hub_page: str
    leaders_page: str
    profile_page: str
    compare_page: str
    manifest_table: str
    players_sport_default: str


def _nfl_meta() -> SportMeta:
    return SportMeta(
        sport_id="nfl",
        label="NFL",
        icon="🏈",
        game_unit="week",
        season_label_hint="Calendar year (e.g. 2023)",
        ingest_command=r".\.venv\Scripts\python.exe scripts\ingest_season.py --season 2023",
        data_source="nflverse / nflreadpy",
        license_note="CC-BY 4.0 (nflverse)",
        hub_page="pages/nfl/0_NFL_Home.py",
        leaders_page="pages/nfl/1_Season_Leaders.py",
        profile_page="pages/2_Player_Profile.py",
        compare_page="pages/3_Compare.py",
        manifest_table="ingest_manifest",
        players_sport_default="nfl",
    )


def _mlb_meta() -> SportMeta:
    return SportMeta(
        sport_id="mlb",
        label="MLB",
        icon="⚾",
        game_unit="game",
        season_label_hint="Calendar year (e.g. 2024)",
        ingest_command=r".\.venv\Scripts\python.exe scripts\ingest_mlb.py --season 2024",
        data_source="pybaseball → Baseball Reference (FanGraphs often 403)",
        license_note="Respect pybaseball/BRef rate limits; attribute Baseball Reference",
        hub_page="pages/mlb/0_MLB_Home.py",
        leaders_page="pages/mlb/1_Season_Leaders.py",
        profile_page="pages/mlb/2_Player_Profile.py",
        compare_page="pages/mlb/3_Compare.py",
        manifest_table="mlb_ingest_manifest",
        players_sport_default="mlb",
    )


def _nba_meta() -> SportMeta:
    return SportMeta(
        sport_id="nba",
        label="NBA",
        icon="🏀",
        game_unit="game",
        season_label_hint="Season end year (e.g. 2024 for 2023–24)",
        ingest_command=r".\.venv\Scripts\python.exe scripts\ingest_nba.py --season 2024",
        data_source="nba_api (NBA Stats API)",
        license_note="Follow NBA.com API terms of use",
        hub_page="pages/nba/0_NBA_Home.py",
        leaders_page="pages/nba/1_Season_Leaders.py",
        profile_page="pages/nba/2_Player_Profile.py",
        compare_page="pages/nba/3_Compare.py",
        manifest_table="nba_ingest_manifest",
        players_sport_default="nba",
    )


def _nhl_meta() -> SportMeta:
    return SportMeta(
        sport_id="nhl",
        label="NHL",
        icon="🏒",
        game_unit="game",
        season_label_hint="Season end year (e.g. 2024 for 2023–24)",
        ingest_command=r".\.venv\Scripts\python.exe scripts\ingest_nhl.py --season 2024",
        data_source="nhl-api-py (NHL API)",
        license_note="NHL API; check package terms",
        hub_page="pages/nhl/0_NHL_Home.py",
        leaders_page="pages/nhl/1_Season_Leaders.py",
        profile_page="pages/nhl/2_Player_Profile.py",
        compare_page="pages/nhl/3_Compare.py",
        manifest_table="nhl_ingest_manifest",
        players_sport_default="nhl",
    )


_REGISTRY: dict[str, SportMeta] = {
    "nfl": _nfl_meta(),
    "mlb": _mlb_meta(),
    "nba": _nba_meta(),
    "nhl": _nhl_meta(),
}


def get_sport(sport_id: str) -> SportMeta:
    key = str(sport_id or DEFAULT_SPORT).strip().lower()
    if key not in _REGISTRY:
        raise ValueError(f"Unknown sport: {sport_id}")
    return _REGISTRY[key]


def list_sports() -> list[SportMeta]:
    return [_REGISTRY[sid] for sid in SPORT_IDS]


def sport_has_ingested_data(conn: duckdb.DuckDBPyConnection, sport_id: str) -> bool:
    meta = get_sport(sport_id)
    if sport_id == "nfl":
        from src.db.connection import list_ingested_seasons

        return bool(list_ingested_seasons(conn, sport="nfl"))
    try:
        row = conn.execute(
            f"SELECT COUNT(*) FROM {meta.manifest_table}"
        ).fetchone()
        return bool(row and row[0] > 0)
    except duckdb.Error:
        return False


def list_sports_with_data(conn: duckdb.DuckDBPyConnection) -> list[SportMeta]:
    return [m for m in list_sports() if sport_has_ingested_data(conn, m.sport_id)]


def leader_position_options(sport_id: str) -> list[str]:
    if sport_id == "nfl":
        from src.sports.nfl.positions import leader_position_options

        return leader_position_options()
    if sport_id == "mlb":
        from src.sports.mlb.positions import leader_position_options

        return leader_position_options()
    if sport_id == "nba":
        from src.sports.nba.positions import leader_position_options

        return leader_position_options()
    if sport_id == "nhl":
        from src.sports.nhl.positions import leader_position_options

        return leader_position_options()
    return []


def default_leader_selection(sport_id: str) -> list[str]:
    sid = sport_id.strip().lower()
    if sid == "nfl":
        from src.sports.nfl.positions import default_leader_selection

        return default_leader_selection()
    if sid == "mlb":
        from src.sports.mlb.positions import default_leader_selection

        return default_leader_selection()
    if sid == "nba":
        from src.sports.nba.positions import default_leader_selection

        return default_leader_selection()
    if sid == "nhl":
        from src.sports.nhl.positions import default_leader_selection

        return default_leader_selection()
    opts = leader_position_options(sid)
    return list(opts[:1]) if opts else []


def season_leaders_window(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    seasons: list[int],
    preset_key: str,
    *,
    positions: list[str] | None = None,
    min_games: int | None = None,
):
    """
    Window leaderboard for a non-NFL sport: sum FP and games across seasons
    (min games applied per season before aggregation).
    """
    if sport_id == "nfl":
        from src.db import queries as nfl_queries

        return nfl_queries.season_leaders_window(
            conn, seasons, preset_key, positions=positions, min_games=min_games
        )
    if not seasons:
        return pd.DataFrame()
    if min_games is None:
        min_games = get_min_games_default()

    frames: list[pd.DataFrame] = []
    for yr in seasons:
        part = season_leaders(
            conn,
            sport_id,
            int(yr),
            preset_key,
            positions=positions,
            min_games=min_games,
        )
        if not part.empty:
            part = part.copy()
            part["season"] = int(yr)
            frames.append(part)

    if not frames:
        return pd.DataFrame()
    per_season = pd.concat(frames, ignore_index=True)
    return aggregate_leader_window(per_season)


def season_leaders(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    season: int,
    preset_key: str,
    *,
    positions: list[str] | None = None,
    team: str | None = None,
    min_games: int | None = None,
    use_team_splits: bool = False,
):
    if sport_id == "nfl":
        from src.db import queries

        return queries.season_leaders(
            conn,
            season,
            preset_key,
            positions=positions,
            team=team,
            min_games=min_games,
            use_team_splits=use_team_splits,
        )
    if sport_id == "mlb":
        from src.sports.mlb import queries as mlb_q

        return mlb_q.season_leaders(
            conn,
            season,
            preset_key,
            positions=positions,
            min_games=min_games,
            team=team,
        )
    if sport_id == "nba":
        from src.sports.nba import queries as nba_q

        return nba_q.season_leaders(
            conn,
            season,
            preset_key,
            positions=positions,
            min_games=min_games,
            team=team,
        )
    if sport_id == "nhl":
        from src.sports.nhl import queries as nhl_q

        return nhl_q.season_leaders(
            conn,
            season,
            preset_key,
            positions=positions,
            min_games=min_games,
            team=team,
        )
    return None
