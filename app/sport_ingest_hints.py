"""Ingest command hints and empty-state copy for sport pages."""

from __future__ import annotations

from src.rankings.fantasypros_limits import FP_SPORT_DRAFT_ECR_MIN_SEASON, sport_draft_ecr_supported
from src.sports.registry import SportMeta, get_sport


def gamelog_ingest_command(sport_id: str, season: int | None = None) -> str:
    sid = sport_id.strip().lower()
    year = season or 2024
    if sid == "mlb":
        return rf".\.venv\Scripts\python.exe scripts\ingest_mlb_gamelogs.py --season {year}"
    if sid == "nba":
        return rf".\.venv\Scripts\python.exe scripts\ingest_nba_gamelogs.py --season {year}"
    if sid == "nhl":
        return rf".\.venv\Scripts\python.exe scripts\ingest_nhl_gamelogs.py --season {year}"
    return ""


def draft_ecr_ingest_command(sport_id: str, season: int) -> str:
    sid = sport_id.strip().lower()
    if sid == "nfl":
        return r".\.venv\Scripts\python.exe scripts\ingest_rankings.py"
    if sid in ("mlb", "nba", "nhl"):
        return (
            rf".\.venv\Scripts\python.exe scripts\ingest_sport_rankings.py "
            f"--sport {sid} --season {season} --draft-only"
        )
    return ""


def no_stats_message(meta: SportMeta) -> str:
    return (
        f"No **{meta.label}** season stats in the database. Run:\n\n"
        f"`{meta.ingest_command}`"
    )


def no_rankings_message(sport_id: str, season: int) -> str:
    meta = get_sport(sport_id)
    if not sport_draft_ecr_supported(sport_id, season):
        return (
            f"Draft expert consensus (FantasyPros) is not available for **{meta.label} {season}**. "
            f"MLB, NBA, and NHL draft ECR is only supported for seasons **"
            f"{FP_SPORT_DRAFT_ECR_MIN_SEASON}** and later; older API calls return "
            "current-era player pools, not historical preseason boards."
        )
    cmd = draft_ecr_ingest_command(sport_id, season)
    return (
        f"No draft expert consensus for **{meta.label} {season}** (or too few matched players). "
        f"Run:\n\n`{cmd}`\n\n"
        "Then check match rate:\n\n"
        f"`scripts\\rankings_coverage.py --sport {sport_id} --season {season}`"
    )


def no_gamelogs_message(sport_id: str, season: int, *, game_unit: str = "game") -> str:
    meta = get_sport(sport_id)
    cmd = gamelog_ingest_command(sport_id, season)
    return (
        f"No **{game_unit}** logs for **{meta.label} {season}**. "
        f"Ingest season stats first, then:\n\n`{cmd}`"
    )
