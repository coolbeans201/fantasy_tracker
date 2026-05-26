"""Shared Player Profile layout for MLB / NBA / NHL."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.career_table import (
    add_highlight_column,
    format_peak_prime_caption,
    prime_season_years,
    style_career_breakdown,
)
from app.charts import season_fantasy_points_chart
from app.components import get_db, query_param_season, render_sidebar
from app.sport_context import init_sport_page
from app.sport_profile_display import (
    PROFILE_META_COLUMNS,
    career_season_totals,
    format_profile_table,
    profile_export_columns,
    render_grouped_career_stats,
    season_detail_heading,
)
from app.sport_profile_entry import player_id_from_profile_link
from app.sport_season_scope import (
    profile_season_scope_caption,
    sync_profile_sidebar_seasons,
)
from src.analytics.metrics import add_fp_per_game, peak_season_year
from src.analytics.peer_z_sport import peer_df_for_entity_season_sport, peer_z_score_sport
from src.analytics.sport_variance import add_volume_flags_sport
from src.db.connection import db_exists
from src.season_selection import format_season_span, metric_window_caption
from src.sports.registry import get_sport
from src.sports.display_stats import display_stats_for_sport
from src.sports.player_career import player_career_seasons
from src.sports.player_seasons import player_seasons_available, stats_table
from src.ui_text import page_title_suffix, section_h3, title_case_ui


def _search_fn(sport_id: str):
    if sport_id == "mlb":
        from src.sports.mlb.queries import search_players

        return search_players
    if sport_id == "nba":
        from src.sports.nba.queries import search_players

        return search_players
    from src.sports.nhl.queries import search_players

    return search_players


def _resolve_detail_season(
    entity_seasons: list[int],
    window_years: set[int],
    controls: dict,
) -> int | None:
    detail_options = sorted(
        (int(s) for s in entity_seasons if int(s) in window_years),
        reverse=True,
    )
    if not detail_options:
        return None
    if controls["is_multi_season"] and len(detail_options) > 1:
        return int(
            st.selectbox(
                title_case_ui("Season"),
                detail_options,
                index=0,
                key="sport_profile_detail_season",
                help="Peer Z and game log use one season at a time.",
            )
        )
    return detail_options[0]


def _render_game_log(
    conn,
    sport_id: str,
    player_id: str,
    detail_season: int,
    *,
    game_unit: str,
) -> None:
    from src.sports.game_logs import load_player_game_log

    games = load_player_game_log(conn, sport_id, player_id, detail_season)
    if games is None:
        return
    if games.empty:
        st.info(f"No {game_unit} log rows ingested for this season.")
        return
    st.markdown(section_h3(f"Game log ({detail_season})"))
    st.caption(
        f"Per-{game_unit} fantasy points and stats. "
        "This is not NFL weekly boom/bust scoring."
    )
    if "fantasy_points" in games.columns:
        fp = games["fantasy_points"]
        c1, c2, c3 = st.columns(3)
        c1.metric(title_case_ui("Best game"), f"{fp.max():.1f} FP")
        c2.metric(title_case_ui("Worst game"), f"{fp.min():.1f} FP")
        season_avg = fp.mean()
        above = float((fp > season_avg).mean()) if len(fp) else 0.0
        c3.metric(title_case_ui("Games above avg"), f"{above * 100:.0f}%")
    st.dataframe(
        format_profile_table(games),
        use_container_width=True,
        hide_index=True,
    )


def render_sport_profile_page(sport_id: str, *, label: str) -> None:
    meta = get_sport(sport_id)
    st.set_page_config(page_title=page_title_suffix(f"{label} Player Profile"), layout="wide")
    init_sport_page(sport_id)

    query_season = query_param_season()
    controls = render_sidebar(
        sport=sport_id,
        default_season=st.session_state.get(f"profile_season_default_{sport_id}")
        or query_season,
        season_options=st.session_state.get(f"profile_entity_seasons_{sport_id}"),
        season_scope_caption=profile_season_scope_caption(
            st.session_state.get(f"profile_entity_seasons_{sport_id}")
        ),
    )
    st.title(title_case_ui("Player Profile"))
    st.caption("Uses **ESPN** default fantasy points (v1).")

    if not db_exists() or not controls["seasons"]:
        st.info(f"Ingest {label} data first.")
        st.stop()

    conn = get_db()
    player_id, _picked, display_name = player_id_from_profile_link(
        conn,
        stats_table=stats_table(sport_id),
        search_players=_search_fn(sport_id),
        sidebar_season=controls.get("season"),
    )

    available = player_seasons_available(conn, sport_id, player_id)
    sync_profile_sidebar_seasons(sport_id, player_id, available, query_season)

    career = player_career_seasons(conn, sport_id, player_id)
    if career.empty:
        st.warning("No season data for this player.")
        st.stop()

    window_years = {int(s) for s in controls["seasons"]}
    career = career[career["season"].astype(int).isin(window_years)].copy()
    if career.empty:
        st.warning("No seasons in the sidebar window for this player.")
        st.stop()

    st.subheader(display_name)
    min_games = controls["min_games"]
    entity_seasons = sorted(career["season"].astype(int).unique(), reverse=True)
    detail_season = _resolve_detail_season(entity_seasons, window_years, controls)
    if detail_season is None:
        st.stop()

    st.markdown(section_h3("Career & window"))
    if controls["is_multi_season"]:
        st.caption(
            f"Totals and season rows for **{format_season_span(controls['seasons'])}**."
        )
    qualified = career[career["games"] >= min_games]
    if controls["is_multi_season"] and not qualified.empty:
        total_fp = float(qualified["fantasy_points"].sum())
        total_games = int(qualified["games"].sum())
        c1, c2, c3 = st.columns(3)
        c1.metric(title_case_ui("Window FP"), f"{total_fp:.1f}")
        c2.metric(
            title_case_ui("Window FP/G"),
            f"{total_fp / total_games:.1f}" if total_games else "—",
        )
        c3.metric(title_case_ui("Qualified seasons"), str(len(qualified)))
    cap = metric_window_caption(controls["seasons"])
    if cap:
        st.caption(cap)

    chart_career = career_season_totals(career)
    show_peak = len(chart_career) > 1
    peak_yr = peak_season_year(chart_career) if show_peak else None
    prime_years = prime_season_years(career)
    peak_cap = format_peak_prime_caption(peak_yr, prime_years)
    if peak_cap:
        st.caption(peak_cap)
    if sport_id == "mlb":
        from src.sports.mlb.seasons import MLB_COVID_SHORTENED_SEASON

        st.caption(
            f"**Career Z** and **peer Z** use min games and position volume gates. "
            f"Career Z is omitted for **{MLB_COVID_SHORTENED_SEASON}** "
            "(COVID-shortened season)."
        )
    else:
        st.caption(
            "**Career Z** and **peer Z** use min games and position volume gates for this sport."
        )

    career_cols = [
        "season",
        "team",
        "position",
        "games",
        "fantasy_points",
        "fp_per_game",
        "career_z",
        "peer_z_season",
    ]
    career_show = career[[c for c in career_cols if c in career.columns]].copy()

    detail_mask = career["season"].astype(int) == detail_season
    detail_rows = career[detail_mask]
    if not detail_rows.empty:
        peer_df = peer_df_for_entity_season_sport(conn, sport_id, detail_season, min_games)
        peer_df = add_volume_flags_sport(peer_df, sport_id, min_games=min_games)
        if "peer_z_season" not in career_show.columns:
            career_show["peer_z_season"] = None
        for idx in detail_rows.index:
            row = career.loc[idx]
            pz = peer_z_score_sport(
                float(row["fantasy_points"]),
                peer_df,
                sport_id,
                row.get("position"),
            )
            career_show.loc[idx, "peer_z_season"] = pz

    season_series = career["season"].astype(int)
    career_highlighted = add_highlight_column(
        format_profile_table(career_show),
        season_series,
        peak_season=peak_yr,
        prime_seasons=prime_years,
    )
    st.dataframe(
        style_career_breakdown(
            career_highlighted,
            season_series,
            peak_season=peak_yr,
            prime_seasons=prime_years,
        ),
        use_container_width=True,
        hide_index=True,
    )
    export_cols = profile_export_columns(sport_id, career)
    st.download_button(
        title_case_ui("Download career CSV"),
        format_profile_table(career, columns=export_cols).to_csv(index=False),
        file_name=f"{sport_id}_profile_{player_id}_career.csv",
        mime="text/csv",
        key=f"profile_career_csv_{sport_id}",
    )

    with st.expander(title_case_ui("All career stats")):
        render_grouped_career_stats(sport_id, career, container=st)

    st.markdown(section_h3("Fantasy points by season"))
    if len(career) > len(chart_career):
        st.caption(
            "Season totals combine every team and role row for that year."
        )
    season_fantasy_points_chart(
        chart_career,
        peak_season=peak_yr,
        prime_seasons=prime_years,
    )

    st.divider()
    st.markdown(section_h3(f"Season detail ({detail_season})"))
    if detail_rows.empty:
        st.warning(f"No row for season {detail_season}.")
    else:
        detail_sorted = detail_rows.sort_values(
            ["position", "team"],
            ascending=[True, True],
            na_position="last",
        )
        multi_stint = len(detail_sorted) > 1
        peer_df = peer_df_for_entity_season_sport(conn, sport_id, detail_season, min_games)
        peer_df = add_volume_flags_sport(peer_df, sport_id, min_games=min_games)
        season_export_parts: list[pd.DataFrame] = []

        for _, sr in detail_sorted.iterrows():
            heading = season_detail_heading(sr, multi=multi_stint)
            if heading:
                st.markdown(f"**{heading}**")
            pos = sr.get("position")
            pz = peer_z_score_sport(
                float(sr["fantasy_points"]),
                peer_df,
                sport_id,
                pos,
            )
            cz = sr.get("career_z")
            c1, c2, c3 = st.columns(3)
            c1.metric(title_case_ui("Fantasy points"), f"{float(sr['fantasy_points']):.1f}")
            c2.metric(
                title_case_ui("Peer Z (season)"),
                f"{pz:+.2f}" if pz is not None else "—",
            )
            c3.metric(
                title_case_ui("Career Z"),
                f"{float(cz):+.2f}" if cz is not None and str(cz) != "nan" else "—",
            )
            stat_cols = display_stats_for_sport(sport_id, str(pos) if pos is not None else None)
            extra_set = frozenset(PROFILE_META_COLUMNS)
            detail_cols = [c for c in PROFILE_META_COLUMNS if c in sr.index]
            detail_cols += [
                c for c in stat_cols if c in sr.index and c not in extra_set
            ]
            row_df = pd.DataFrame([sr])
            shown = format_profile_table(row_df, columns=detail_cols)
            season_export_parts.append(shown)
            st.dataframe(shown, use_container_width=True, hide_index=True)

        season_csv = pd.concat(season_export_parts, ignore_index=True)
        st.download_button(
            title_case_ui("Download season CSV"),
            season_csv.to_csv(index=False),
            file_name=f"{sport_id}_profile_{player_id}_{detail_season}.csv",
            mime="text/csv",
            key=f"profile_season_csv_{sport_id}",
        )

    _render_game_log(conn, sport_id, player_id, detail_season, game_unit=meta.game_unit)
