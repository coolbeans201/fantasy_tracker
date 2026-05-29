"""Shared Player Profile layout for MLB / NBA / NHL (pane order matches NFL profile)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.career_table import (
    add_highlight_column,
    format_peak_prime_caption,
    prime_season_years,
    style_career_breakdown,
)
from app.charts import game_log_fantasy_points_chart, season_fantasy_points_chart
from app.game_log_table import add_game_highlight_column, style_game_log_table
from app.components import get_db, query_param_season, render_sidebar
from app.sport_context import init_sport_page
from app.sport_profile_display import (
    PROFILE_META_COLUMNS,
    career_season_totals,
    format_game_log_table,
    format_profile_table,
    profile_export_columns,
    render_grouped_career_stats,
)
from app.sport_profile_entry import player_id_from_profile_link
from app.sport_season_scope import (
    profile_season_scope_caption,
    sync_profile_sidebar_seasons,
)
from app.surprise_ui import render_surprise_metrics_row
from src.analytics.metrics import peak_season_year
from src.analytics.sport_surprise import season_surprise_for_entity_sport
from src.analytics.peer_z_sport import peer_df_for_entity_season_sport, peer_z_score_sport
from src.analytics.sport_variance import add_volume_flags_sport
from src.db.connection import db_exists
from src.db.queries import season_has_rankings
from src.season_selection import format_season_span, metric_window_caption
from src.sports.display_stats import display_stats_for_sport
from src.sports.player_career import player_career_seasons, sort_career_rows
from src.sports.player_seasons import player_seasons_available, stats_table
from src.sports.registry import get_sport
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
                help="Peer Z, consistency, and game log are for one season at a time.",
            )
        )
    return detail_options[0]


def _career_show_with_peer_z(
    conn,
    sport_id: str,
    career: pd.DataFrame,
    min_games: int,
) -> pd.DataFrame:
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
    if "peer_z_season" not in career_show.columns:
        career_show["peer_z_season"] = None
    for season_val, season_rows in career.groupby(career["season"].astype(int)):
        peer_df = peer_df_for_entity_season_sport(conn, sport_id, int(season_val), min_games)
        peer_df = add_volume_flags_sport(peer_df, sport_id, min_games=min_games)
        for idx in season_rows.index:
            row = career.loc[idx]
            pz = peer_z_score_sport(
                float(row["fantasy_points"]),
                peer_df,
                sport_id,
                row.get("position"),
            )
            career_show.loc[idx, "peer_z_season"] = pz
    return career_show


def _render_career_window_section(
    *,
    sport_id: str,
    player_id: str,
    career: pd.DataFrame,
    career_show: pd.DataFrame,
    chart_career: pd.DataFrame,
    controls: dict,
    min_games: int,
    peak_yr: int | None,
    prime_years: list[int],
    show_peak_highlight: bool,
) -> None:
    """Career pane: window summary, season table, exports, season chart (NFL order)."""
    st.markdown(section_h3("Career & window"))
    if controls["is_multi_season"]:
        st.caption(
            f"Totals and season rows for the sidebar window "
            f"(**{format_season_span(controls['seasons'])}**)."
        )
    else:
        st.caption("Season-by-season career view for the year selected in the sidebar.")

    qualified_flags = add_volume_flags_sport(career, sport_id, min_games=min_games)
    qualified = qualified_flags[qualified_flags["peer_qualified"]]
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

    peak_cap = format_peak_prime_caption(peak_yr, prime_years)
    if peak_cap:
        st.caption(peak_cap)

    highlight_note = (
        " See **Highlight** column and chart legend when a season is peak, prime, or both."
        if show_peak_highlight
        else " **Prime** seasons (career Z > 1) are highlighted in green when applicable."
    )
    if sport_id == "mlb":
        from src.sports.mlb.seasons import MLB_COVID_SHORTENED_SEASON

        st.caption(
            f"**Career Z** and peer gates use min games and position volume rules. "
            f"Career Z is omitted for **{MLB_COVID_SHORTENED_SEASON}** "
            f"(COVID-shortened season).{highlight_note}"
        )
    else:
        st.caption(
            "**Career Z** and peer gates use min games and position volume rules "
            f"for this sport.{highlight_note}"
        )

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
        st.caption("Season totals combine every team and role row for that year.")
    if show_peak_highlight:
        st.caption(
            "Orange = peak FP · green = prime only · orange with green ring = **peak and prime** "
            "same season."
        )
    elif prime_years:
        st.caption("Green = prime season (career Z > 1).")
    season_fantasy_points_chart(
        chart_career,
        peak_season=peak_yr,
        prime_seasons=prime_years,
    )


def _render_season_detail_section(
    *,
    conn,
    sport_id: str,
    player_id: str,
    detail_season: int,
    detail_rows: pd.DataFrame,
    career: pd.DataFrame,
    min_games: int,
    game_unit: str,
    preset_key: str,
) -> None:
    """Season pane: snapshot, splits, game chart, game table (mirrors NFL weekly layout)."""
    st.divider()
    st.markdown(section_h3(f"Season detail ({detail_season})"))
    st.caption(
        f"Peer Z (season), per-{game_unit} consistency, and the {game_unit} log apply to "
        "this season only."
    )

    detail_sorted = sort_career_rows(detail_rows)
    primary = detail_sorted.sort_values("games", ascending=False).iloc[0]
    total_fp = float(detail_sorted["fantasy_points"].sum())
    total_games = int(detail_sorted["games"].sum())
    multi_stint = len(detail_sorted) > 1

    peer_df = peer_df_for_entity_season_sport(conn, sport_id, detail_season, min_games)
    peer_df = add_volume_flags_sport(peer_df, sport_id, min_games=min_games)
    peer_z = peer_z_score_sport(
        total_fp,
        peer_df,
        sport_id,
        primary.get("position"),
    )

    cz_row = career[career["season"].astype(int) == detail_season]
    career_z = None
    if not cz_row.empty and "career_z" in cz_row.columns:
        cz_primary = cz_row.sort_values("games", ascending=False).iloc[0]
        val = cz_primary.get("career_z")
        if val is not None and str(val) != "nan":
            career_z = float(val)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(title_case_ui("Season FP"), f"{total_fp:.1f}")
    c2.metric(
        title_case_ui("FP per game"),
        f"{total_fp / total_games:.1f}" if total_games else "—",
    )
    c3.metric(
        title_case_ui("Peer Z (season)"),
        f"{peer_z:+.2f}" if peer_z is not None else "—",
    )
    surprise = None
    if season_has_rankings(conn, detail_season, sport=sport_id):
        surprise = season_surprise_for_entity_sport(
            conn,
            sport_id,
            player_id,
            detail_season,
            preset_key,
            min_games=min_games,
            position=primary.get("position"),
        )
    used_c4 = False
    if surprise:
        c4.metric(title_case_ui("Rank Δ vs draft"), f"{surprise['rank_delta']:+d}")
        used_c4 = True
    elif career_z is not None:
        c4.metric(title_case_ui("Career Z"), f"{career_z:+.2f}")
        used_c4 = True
    elif not used_c4:
        c4.metric(title_case_ui("Career Z"), "—")
    render_surprise_metrics_row(surprise)

    if multi_stint:
        st.markdown(section_h3(f"Team / role splits ({detail_season})"))
        if sport_id in ("mlb", "nhl"):
            from app.sport_profile_display import render_grouped_career_stats

            render_grouped_career_stats(sport_id, detail_sorted, container=st)
            if sport_id == "mlb" and len(detail_sorted) > 1:
                st.caption(
                    "Season FP and FP per game above combine every role row for this year."
                )
        else:
            split_cols = [
                c
                for c in ["team", "position", "games", "fantasy_points", "fp_per_game"]
                if c in detail_sorted.columns
            ]
            pos = primary.get("position")
            stat_cols = display_stats_for_sport(
                sport_id, str(pos) if pos is not None else None
            )
            split_cols += [
                c for c in stat_cols if c in detail_sorted.columns and c not in split_cols
            ]
            st.dataframe(
                format_profile_table(detail_sorted, columns=split_cols),
                use_container_width=True,
                hide_index=True,
            )

    from src.analytics.game_consistency import (
        consistency_from_games,
        format_game_boom_bust_caption,
        player_game_fp_percentiles,
    )
    from src.sports.game_logs import filter_game_log_for_profile, load_player_game_log

    games = load_player_game_log(conn, sport_id, player_id, detail_season)
    if games is None:
        return
    if games.empty:
        st.info(f"No {game_unit} log rows ingested for this season.")
        return

    profile_pos = primary.get("position")
    gamelog_log_type: str | None = None
    gamelog_display_pos = profile_pos

    if sport_id == "mlb":
        from src.sports.game_logs import (
            MLB_LOG_HITTING,
            MLB_LOG_PITCHING,
            enrich_mlb_game_log_rows,
            mlb_default_game_log_type,
            mlb_game_log_types_present,
            mlb_position_for_game_log_type,
        )

        from src.sports.game_logs import mlb_two_way_career, mlb_two_way_season

        games = enrich_mlb_game_log_rows(games)
        log_types = mlb_game_log_types_present(games)
        two_way = mlb_two_way_season(conn, player_id, detail_season)
        career_two_way = mlb_two_way_career(conn, player_id)
        default_type = mlb_default_game_log_type(
            detail_sorted, games, primary_position=profile_pos
        )
        options = [MLB_LOG_HITTING, MLB_LOG_PITCHING]
        labels = {MLB_LOG_HITTING: "Hitting", MLB_LOG_PITCHING: "Pitching"}
        show_role_picker = career_two_way or two_way or len(log_types) > 1

        if show_role_picker:
            gamelog_log_type = st.radio(
                title_case_ui("Game log view"),
                options,
                format_func=lambda v: labels.get(v, str(v).title()),
                horizontal=True,
                index=options.index(default_type) if default_type in options else 0,
                key=f"mlb_profile_gamelog_{player_id}_{detail_season}",
                help=(
                    "Two-way players store separate hitting and pitching rows per game. "
                    "Pick which role to show (not one combined row)."
                ),
            )
            from src.sports.game_logs import MLB_MAX_REGULAR_GAMES, count_distinct_games

            role_games = filter_game_log_for_profile(
                games,
                sport_id,
                profile_pos,
                log_type=gamelog_log_type,
            )
            chosen_count = count_distinct_games(role_games)
            if chosen_count == 0:
                st.warning(
                    f"No **{labels[gamelog_log_type]}** rows in the database for {detail_season}. "
                    "Re-ingest game logs with: "
                    f"`scripts/ingest_mlb_gamelogs.py --season {detail_season} --refresh-cache`"
                )
            else:
                reg_note = ""
                if chosen_count > MLB_MAX_REGULAR_GAMES:
                    reg_note = (
                        f" ({chosen_count} rows looks high — re-ingest with regular-season "
                        f"filter: `ingest_mlb_gamelogs.py --season {detail_season} --refresh-cache`)"
                    )
                st.caption(
                    f"Showing **{labels[gamelog_log_type]}** — **{chosen_count}** regular-season "
                    f"{game_unit}s (one row per {game_unit}, not merged with the other role)."
                    f"{reg_note}"
                )
        elif log_types:
            gamelog_log_type = default_type
            st.caption(
                f"Game log shows **{labels.get(gamelog_log_type, gamelog_log_type.title())}** "
                f"for this season."
            )
        elif profile_pos:
            gamelog_log_type = default_type
            role = "Pitching" if gamelog_log_type == MLB_LOG_PITCHING else "Hitting"
            st.caption(
                f"Game log uses **{role}** (primary season role: {profile_pos})."
            )

        if gamelog_log_type:
            gamelog_display_pos = mlb_position_for_game_log_type(gamelog_log_type)

    games = filter_game_log_for_profile(
        games,
        sport_id,
        profile_pos,
        log_type=gamelog_log_type,
    )
    if games.empty:
        st.info(f"No {game_unit} log rows for this role in {detail_season}.")
        return

    p25, p75 = player_game_fp_percentiles(games)
    game_metrics = consistency_from_games(games, p25=p25, p75=p75)

    if "fantasy_points" in games.columns:
        fp = games["fantasy_points"]
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric(title_case_ui("Best game"), f"{fp.max():.1f} FP")
        m2.metric(title_case_ui("Worst game"), f"{fp.min():.1f} FP")
        season_avg = fp.mean()
        above = float((fp > season_avg).mean()) if len(fp) else 0.0
        m3.metric(title_case_ui("Games above avg"), f"{above * 100:.0f}%")
        boom = game_metrics.get("boom_rate")
        bust = game_metrics.get("bust_rate")
        m4.metric(
            title_case_ui("Strong game rate"),
            f"{boom * 100:.0f}%" if boom is not None else "—",
        )
        m5.metric(
            title_case_ui("Weak game rate"),
            f"{bust * 100:.0f}%" if bust is not None else "—",
        )
        st.caption(format_game_boom_bust_caption(p25, p75, game_unit=game_unit))

    unit_label = game_unit.capitalize()
    st.markdown(section_h3(f"Fantasy points by {game_unit}"))
    st.caption("Dashed line = season average for this player.")
    game_log_fantasy_points_chart(games, p25=p25, p75=p75)

    st.markdown(section_h3(f"{unit_label} log"))
    if "opponent" in games.columns and games["opponent"].isna().all():
        st.caption("Opponent not loaded for this season yet — re-ingest game logs if needed.")
    if sport_id == "mlb" and gamelog_log_type == MLB_LOG_PITCHING:
        if not any(
            c in games.columns and games[c].notna().any()
            for c in ("wins", "strikeouts_pitch", "innings_pitched")
        ):
            st.caption(
                "Pitching box-score columns missing — re-run "
                "`scripts/ingest_mlb_gamelogs.py --season "
                f"{detail_season} --refresh-cache` after updating."
            )
    elif sport_id == "mlb" and gamelog_log_type == MLB_LOG_HITTING:
        if not any(
            c in games.columns and games[c].notna().any()
            for c in ("runs", "home_runs", "rbi")
        ):
            st.caption(
                "Hitting box-score columns missing — re-run "
                "`scripts/ingest_mlb_gamelogs.py --season "
                f"{detail_season} --refresh-cache` after updating."
            )
    elif sport_id == "mlb" and not any(
        c in games.columns and games[c].notna().any()
        for c in ("runs", "wins", "innings_pitched")
    ):
        st.caption(
            "Box-score columns missing — re-run "
            "`scripts/ingest_mlb_gamelogs.py --season "
            f"{detail_season} --refresh-cache` after updating."
        )
    if sport_id == "nhl":
        from src.sports.nhl.positions import is_goalie_position

        if is_goalie_position(profile_pos):
            if not any(
                c in games.columns and games[c].notna().any()
                for c in ("saves", "goals_against", "wins")
            ):
                st.caption(
                    "Goalie box-score columns missing — re-run "
                    f"`scripts/ingest_nhl_gamelogs.py --season {detail_season} "
                    "--refresh-cache`."
                )
        elif not any(
            c in games.columns and games[c].notna().any() for c in ("goals", "assists", "shots")
        ):
            st.caption(
                "Skater box-score columns missing — re-run "
                f"`scripts/ingest_nhl_gamelogs.py --season {detail_season} --refresh-cache`."
            )
    log_show = format_game_log_table(
        games,
        sport_id,
        str(gamelog_display_pos if sport_id == "mlb" else profile_pos)
        if (gamelog_display_pos or profile_pos) is not None
        else None,
        log_type=gamelog_log_type if sport_id in ("mlb", "nhl") else None,
    )
    log_show = add_game_highlight_column(log_show, games, p25=p25, p75=p75)
    styled_log = style_game_log_table(log_show, games, p25=p25, p75=p75)
    st.dataframe(styled_log, use_container_width=True, hide_index=True)
    st.download_button(
        title_case_ui(f"Download {game_unit} log CSV"),
        log_show.to_csv(index=False),
        file_name=f"{sport_id}_profile_{player_id}_{detail_season}_{game_unit}_log.csv",
        mime="text/csv",
        key=f"profile_gamelog_csv_{sport_id}_{detail_season}",
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

    min_games = controls["min_games"]
    primary_pos = ""
    if "position" in career.columns and career["position"].notna().any():
        primary_pos = str(career["position"].dropna().iloc[-1]).strip()
    header = f"{display_name} ({primary_pos})" if primary_pos else display_name
    st.subheader(header)

    chart_career = career_season_totals(career)
    show_peak_highlight = len(chart_career) > 1
    peak_yr = peak_season_year(chart_career) if show_peak_highlight else None
    prime_years = prime_season_years(career)
    career_show = _career_show_with_peer_z(conn, sport_id, career, min_games)

    _render_career_window_section(
        sport_id=sport_id,
        player_id=player_id,
        career=career,
        career_show=career_show,
        chart_career=chart_career,
        controls=controls,
        min_games=min_games,
        peak_yr=peak_yr,
        prime_years=prime_years,
        show_peak_highlight=show_peak_highlight,
    )

    entity_seasons = sorted(career["season"].astype(int).unique(), reverse=True)
    detail_season = _resolve_detail_season(entity_seasons, window_years, controls)
    if detail_season is not None:
        detail_rows = career[career["season"].astype(int) == detail_season]
        if not detail_rows.empty:
            _render_season_detail_section(
                conn=conn,
                sport_id=sport_id,
                player_id=player_id,
                detail_season=detail_season,
                detail_rows=detail_rows,
                career=career,
                min_games=min_games,
                game_unit=meta.game_unit,
                preset_key=controls["preset_key"],
            )
