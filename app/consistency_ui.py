"""Streamlit UI for weekly consistency / boom-bust metrics."""

from __future__ import annotations

import streamlit as st

from src.ui_text import section_h3, title_case_ui


def render_consistency_panel(
    metrics: dict[str, float | int | None],
    *,
    season: int,
    position_label: str | None = None,
    heading: str | None = None,
) -> None:
    """Prominent weekly σ and boom/bust metrics (Player Profile / Compare)."""
    pos_note = f" ({position_label})" if position_label else ""
    title = heading or f"Weekly consistency ({season})"
    st.markdown(section_h3(title))

    std = metrics.get("weekly_std")
    boom = metrics.get("boom_rate")
    bust = metrics.get("bust_rate")
    worst = metrics.get("worst_week_fp")
    weeks = metrics.get("weeks_played", 0)

    if std is None and boom is None and bust is None:
        st.info("Not enough weekly data to compute consistency metrics for this season.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "Weekly σ",
        f"{std:.1f}" if std is not None else "—",
        help=(
            "Standard deviation of weekly fantasy points. "
            "Lower values usually mean a steadier week-to-week floor."
        ),
    )
    c2.metric(
        title_case_ui("Boom rate"),
        f"{boom * 100:.0f}%" if boom is not None else "—",
        help=(
            "Share of weeks at or above the 75th-percentile weekly FP "
            f"for this position{pos_note} in {season}."
        ),
    )
    c3.metric(
        title_case_ui("Bust rate"),
        f"{bust * 100:.0f}%" if bust is not None else "—",
        help=(
            "Share of weeks at or below the 25th-percentile weekly FP "
            f"for this position{pos_note} in {season}."
        ),
    )
    c4.metric(
        title_case_ui("Worst week"),
        f"{worst:.1f}" if worst is not None else "—",
        help="Lowest single-week fantasy point total in the regular season.",
    )
    c5.metric(
        "Weeks",
        str(weeks) if weeks else "—",
        help="Regular-season weeks with stored weekly stats.",
    )

    st.caption(
        "Boom/bust thresholds use P25/P75 of **qualified** player-weeks "
        f"for {position_label or 'this position'} in {season} "
        "(weekly volume gates match peer Z rules, prorated per game). "
        "DST uses all team-weeks."
    )


def render_game_consistency_panel(
    metrics: dict[str, float | int | None],
    *,
    season: int,
    game_unit: str = "game",
    position_label: str | None = None,
    heading: str | None = None,
) -> None:
    """Per-game σ and boom/bust (player-relative thresholds)."""
    pos_note = f" ({position_label})" if position_label else ""
    title = heading or f"Per-{game_unit} consistency ({season})"
    st.markdown(section_h3(title))

    std = metrics.get("game_std")
    boom = metrics.get("boom_rate")
    bust = metrics.get("bust_rate")
    worst = metrics.get("worst_game_fp")
    games_n = metrics.get("games_played", 0)

    if std is None and boom is None and bust is None:
        st.info(
            f"Not enough {game_unit} logs to compute consistency for this season."
        )
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        title_case_ui(f"{game_unit.title()} σ"),
        f"{std:.1f}" if std is not None else "—",
        help=f"Standard deviation of fantasy points across {game_unit}s in the loaded log.",
    )
    c2.metric(
        title_case_ui("Strong rate"),
        f"{boom * 100:.0f}%" if boom is not None else "—",
        help=f"Share of {game_unit}s at or above this player's top quartile FP.",
    )
    c3.metric(
        title_case_ui("Weak rate"),
        f"{bust * 100:.0f}%" if bust is not None else "—",
        help=f"Share of {game_unit}s at or below this player's bottom quartile FP.",
    )
    c4.metric(
        title_case_ui(f"Worst {game_unit}"),
        f"{worst:.1f}" if worst is not None else "—",
    )
    c5.metric(title_case_ui(f"{game_unit.title()}s"), str(games_n) if games_n else "—")
    st.caption(
        f"Thresholds use this player's own {game_unit} distribution{pos_note}, "
        "not league peers."
    )
