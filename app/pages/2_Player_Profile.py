"""Player Profile page (players and team defenses)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from app.career_table import (
    add_highlight_column,
    format_peak_prime_caption,
    prime_season_years,
    style_career_breakdown,
)
from app.charts import season_fantasy_points_chart, weekly_fantasy_points_chart
from app.components import (
    fuzzy_entity_select,
    get_db,
    query_param_entity,
    query_param_season,
    render_sidebar,
)
from app.consistency_ui import render_consistency_panel
from app.surprise_ui import render_surprise_metrics_row
from app.weekly_table import add_weekly_highlight_column, style_weekly_breakdown
from src.analytics.surprise import enrich_weekly_with_surprise, season_surprise_for_entity
from src.db.queries import season_has_rankings
from src.analytics.best_week import overlay_preset_best_week, preset_best_week_label
from src.analytics.consistency import (
    consistency_from_weekly,
    format_weekly_boom_bust_caption,
    position_weekly_percentiles,
)
from src.analytics.metrics import add_fp_per_game, peak_season_year
from src.analytics.peer_z import (
    add_peer_z_era_column,
    peer_df_for_entity_season,
    peer_z_score,
)
from src.analytics.variance import add_volume_flags, compute_career_z, load_thresholds
from src.db.connection import db_exists
from src.db.queries import (
    entity_all_weekly,
    entity_seasons,
    entity_weekly,
    player_team_splits,
    season_stats_for_peer_analysis,
)
from src.entities import dst_display_name, dst_team_from_entity, is_dst_entity
from src.positions import DST_POSITION, normalize_fantasy_position
from src.season_selection import format_season_span, metric_window_caption
from src.stats_columns import display_stats_for_positions, rename_stats_for_display
from src.ui_text import (
    best_week_fp_column_label,
    page_title_suffix,
    section_h3,
    title_case_ui,
)


def _profile_season_scope_caption(seasons: list[int] | None) -> str | None:
    if not seasons:
        return None
    if len(seasons) == 1:
        return f"Season list: this player's **{seasons[0]}** season only."
    return (
        f"Season list: this player's career (**{seasons[-1]}–{seasons[0]}**, "
        f"{len(seasons)} seasons)."
    )


def _sync_profile_sidebar_seasons(
    entity_id: str,
    available: list[int],
    query_season: int | None,
) -> None:
    """Limit sidebar seasons to the selected entity; rerun once when the list changes."""
    prev_entity = st.session_state.get("profile_seasons_entity")
    st.session_state["profile_entity_seasons"] = available

    if not available:
        return

    if entity_id != prev_entity:
        st.session_state["profile_seasons_entity"] = entity_id
        if query_season in available:
            st.session_state["profile_season_default"] = query_season
        else:
            st.session_state["profile_season_default"] = max(available)
        st.rerun()

    current_default = st.session_state.get("profile_season_default")
    if current_default not in available:
        st.session_state["profile_season_default"] = (
            query_season if query_season in available else max(available)
        )
        st.rerun()


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
                key="profile_detail_season",
                help="Peer Z, consistency, and weekly stats are for one season at a time.",
            )
        )
    return detail_options[0]


def _render_career_window_section(
    *,
    career: pd.DataFrame,
    career_show: pd.DataFrame,
    career_cols: list[str],
    entity_id: str,
    primary_pos: str,
    dst_view: bool,
    conn,
    preset_key: str,
    min_games: int,
    controls: dict,
    stat_cols: list[str],
) -> None:
    """Multi-season / career view: window summary, season table, chart, exports."""
    st.markdown(section_h3("Career & window"))
    if controls["is_multi_season"]:
        st.caption(
            f"Totals and season rows for the sidebar window "
            f"(**{format_season_span(controls['seasons'])}**)."
        )
    else:
        st.caption("Season-by-season career view for the year selected in the sidebar.")

    if controls["is_multi_season"] and not career.empty:
        if not dst_view:
            qualified = career[career["games"] >= min_games]
        else:
            qualified = career
        if qualified.empty:
            st.caption(f"No seasons in this window meet the min **{min_games}** games rule.")
        else:
            total_fp = float(qualified["fantasy_points"].sum())
            total_games = int(qualified["games"].sum())
            c1, c2, c3 = st.columns(3)
            c1.metric("Window FP", f"{total_fp:.1f}")
            c2.metric("Window FP/G", f"{total_fp / total_games:.1f}" if total_games else "—")
            c3.metric("Qualified seasons", str(len(qualified)))
        cap = metric_window_caption(controls["seasons"])
        if cap:
            st.caption(cap)

    # Peak is only meaningful with 2+ seasons in view; one sidebar year is trivially "peak".
    show_peak_highlight = len(career) > 1
    peak_yr = peak_season_year(career) if show_peak_highlight else None
    prime_years = prime_season_years(career)
    peak_prime_caption = format_peak_prime_caption(peak_yr, prime_years)
    if peak_prime_caption:
        st.caption(peak_prime_caption)

    if dst_view:
        dst_note = (
            " Orange = peak FP, green = prime, orange with green ring = both."
            if show_peak_highlight
            else " Green = prime season (career Z > 1) when applicable."
        )
        st.caption(
            "One row per season for this team's defense. **Career Z** uses all seasons with "
            f"games played (min games filter does not apply to DST).{dst_note}"
        )
    else:
        highlight_note = (
            " See **Highlight** column and chart legend when a season is peak, prime, or both."
            if show_peak_highlight
            else " **Prime** seasons (career Z > 1) are highlighted in green when applicable."
        )
        st.caption(
            "**Career Z** and peer gates use min games and position volume rules. "
            f"**Best week** uses weekly peaks for the sidebar preset "
            f"({preset_best_week_label(preset_key, conn)}).{highlight_note}"
        )

    season_series = career["season"].astype(int)
    career_highlighted = add_highlight_column(
        career_show,
        season_series,
        peak_season=peak_yr,
        prime_seasons=prime_years,
    )
    styled_career = style_career_breakdown(
        career_highlighted,
        season_series,
        peak_season=peak_yr,
        prime_seasons=prime_years,
    )
    st.dataframe(styled_career, use_container_width=True, hide_index=True)

    st.download_button(
        title_case_ui("Download career CSV"),
        career[career_cols].to_csv(index=False),
        file_name=f"profile_{entity_id.replace(':', '_')}_career.csv",
        mime="text/csv",
        key="profile_career_csv",
    )

    with st.expander(title_case_ui("All career stats")):
        all_career = ["season", "teams", "games", "fantasy_points", "fp_per_game"] + [
            c for c in display_stats_for_positions([primary_pos]) if c in career.columns
        ]
        st.dataframe(
            rename_stats_for_display(career[all_career]),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(section_h3("Fantasy points by season"))
    if dst_view and len(career) >= 15:
        st.caption("Long career span — axis shows every few seasons for readability.")
    if show_peak_highlight:
        st.caption(
            "Orange = peak FP · green = prime only · orange with green ring = **peak and prime** "
            "same season."
        )
    elif prime_years:
        st.caption("Green = prime season (career Z > 1).")
    season_fantasy_points_chart(
        career,
        dense=dst_view,
        peak_season=peak_yr,
        prime_seasons=prime_years,
    )


def _render_season_detail_section(
    *,
    conn,
    entity_id: str,
    detail_season: int,
    season_row: pd.Series,
    career: pd.DataFrame,
    dst_view: bool,
    preset_key: str,
    min_games: int,
    primary_pos: str,
    stat_cols: list[str],
) -> None:
    """One season: snapshot, splits, consistency, weekly chart and table."""
    st.divider()
    st.markdown(section_h3(f"Season detail ({detail_season})"))
    st.caption(
        "Peer Z (season), consistency, boom/bust weeks, and the weekly table apply to "
        "this season only."
    )

    thresholds = load_thresholds()
    peer_df = peer_df_for_entity_season(
        conn,
        detail_season,
        preset_key,
        season_row["position"],
        min_games,
    )
    if not dst_view:
        peer_df = add_volume_flags(peer_df, min_games=min_games)
    fp = float(season_row["fantasy_points"])
    games = int(season_row.get("games", 0) or 0)
    peer_z = peer_z_score(
        fp,
        peer_df,
        season_row["position"],
        min_peers=thresholds.get("min_qualified_peers", 10),
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Season FP", f"{fp:.1f}")
    c2.metric("FP per game", f"{fp / games:.1f}" if games else "—")
    if peer_z is not None:
        c3.metric("Peer Z (season)", f"{peer_z:.2f}")
    surprise = None
    if season_has_rankings(conn, detail_season):
        surprise = season_surprise_for_entity(
            conn, entity_id, detail_season, preset_key, min_games=min_games
        )
    used_c4 = False
    if surprise:
        c4.metric("Rank Δ vs draft", f"{surprise['rank_delta']:+d}")
        used_c4 = True
    cz_row = career[career["season"].astype(int) == detail_season]
    if (
        not used_c4
        and not cz_row.empty
        and "career_z" in cz_row.columns
        and bool(cz_row["peer_qualified"].iloc[0])
        and not np.isnan(cz_row["career_z"].iloc[0])
    ):
        c4.metric("Career Z (this season)", f"{cz_row['career_z'].iloc[0]:.2f}")
    render_surprise_metrics_row(surprise)

    if not dst_view:
        splits = player_team_splits(conn, entity_id, detail_season, preset_key)
        if len(splits) > 1:
            st.markdown(section_h3(f"Team splits ({detail_season})"))
            split_cols = ["team", "games", "fantasy_points", "fp_per_game"] + [
                c for c in stat_cols if c in splits.columns
            ]
            splits = add_fp_per_game(splits)
            st.dataframe(
                rename_stats_for_display(splits[split_cols]),
                use_container_width=True,
                hide_index=True,
            )

    weekly = entity_weekly(conn, entity_id, detail_season, preset_key)
    if weekly.empty:
        st.info(f"No weekly rows for {detail_season}.")
        return

    if season_has_rankings(conn, detail_season) and not dst_view:
        weekly = enrich_weekly_with_surprise(
            conn,
            weekly,
            detail_season,
            preset_key,
            str(season_row.get("position", primary_pos)),
        )

    pos_label = str(season_row.get("position", primary_pos))
    p25, p75 = position_weekly_percentiles(
        conn, detail_season, season_row["position"], preset_key
    )
    consistency_metrics = consistency_from_weekly(weekly, p25=p25, p75=p75)
    render_consistency_panel(
        consistency_metrics,
        season=detail_season,
        position_label=pos_label,
    )
    st.caption(format_weekly_boom_bust_caption(p25, p75, position_label=pos_label))

    st.markdown(section_h3(f"Weekly fantasy points ({detail_season})"))
    weekly_fantasy_points_chart(weekly, p25=p25, p75=p75)

    st.markdown(section_h3(f"Weekly table ({detail_season})"))
    if "opponent" in weekly.columns and weekly["opponent"].isna().all():
        st.caption(
            "Opponent not loaded yet — use sidebar **Repair database** or re-ingest this season."
        )
    week_cols = ["week", "fantasy_points"]
    for extra in ("weekly_ecr", "finish_rank", "rank_delta"):
        if extra in weekly.columns:
            week_cols.append(extra)
    week_cols += [c for c in stat_cols if c in weekly.columns]
    if "opponent" in weekly.columns:
        week_cols.insert(1, "opponent")
    if not dst_view:
        insert_at = 2 if "opponent" in week_cols else 1
        week_cols.insert(insert_at, "team")
    weekly_show = rename_stats_for_display(weekly[week_cols])
    weekly_show = add_weekly_highlight_column(weekly_show, weekly, p25=p25, p75=p75)
    styled_weekly = style_weekly_breakdown(weekly_show, weekly, p25=p25, p75=p75)
    st.dataframe(styled_weekly, use_container_width=True, hide_index=True)
    st.download_button(
        title_case_ui("Download weekly CSV"),
        weekly[week_cols].to_csv(index=False),
        file_name=f"profile_{entity_id.replace(':', '_')}_{detail_season}_weekly.csv",
        mime="text/csv",
        key="profile_weekly_csv",
    )


st.set_page_config(page_title=page_title_suffix("Player Profile"), layout="wide")

_query_season = query_param_season()
controls = render_sidebar(
    default_season=st.session_state.get("profile_season_default") or _query_season,
    season_options=st.session_state.get("profile_entity_seasons"),
    season_scope_caption=_profile_season_scope_caption(
        st.session_state.get("profile_entity_seasons")
    ),
)
st.title("Player Profile")
st.caption("Search for a player (QB/RB/WR/TE/K) or a team defense (e.g. DEN).")

if not db_exists():
    st.info("Ingest at least one completed season to use this page.")
    st.stop()

conn = get_db()

if st.session_state.get("profile_entity_id"):
    entity_id = st.session_state.pop("profile_entity_id")
elif query_param_entity():
    entity_id = query_param_entity()
    st.caption(f"Loaded from link: `{entity_id}`")
    if st.button("Clear link", key="profile_clear_link"):
        st.query_params.clear()
        st.rerun()
else:
    entity_id = fuzzy_entity_select("player or defense", conn, key="profile_entity")

if not entity_id:
    st.stop()

dst_view = is_dst_entity(entity_id)
preset_key = controls["preset_key"]
min_games = controls["min_games"]
seasons_df = entity_seasons(conn, entity_id, preset_key)

if seasons_df.empty:
    st.warning("No season data for this selection.")
    st.stop()

_entity_seasons = sorted(
    (int(s) for s in seasons_df["season"].dropna().unique()), reverse=True
)
_sync_profile_sidebar_seasons(entity_id, _entity_seasons, _query_season)

weekly_all = entity_all_weekly(conn, entity_id, preset_key)
seasons_df = overlay_preset_best_week(seasons_df, weekly_all, preset_key, dst=dst_view)

if dst_view:
    team = dst_team_from_entity(entity_id)
    display_name = dst_display_name(team)
    primary_pos = DST_POSITION
    st.subheader(f"{display_name} ({primary_pos})")
    st.caption("Fantasy points use ESPN default D/ST scoring (not the sidebar offensive preset).")
else:
    display_name = (
        seasons_df["player_name"].iloc[0]
        if "player_name" in seasons_df.columns
        else entity_id
    )
    primary_pos = (
        normalize_fantasy_position(seasons_df["position"].iloc[-1])
        or seasons_df["position"].iloc[-1]
    )
    st.subheader(f"{display_name} ({primary_pos})")

career = compute_career_z(seasons_df, min_games=min_games)
career = add_fp_per_game(career)

window_years = {int(s) for s in controls["seasons"]}
career = career[career["season"].astype(int).isin(window_years)].copy()
if career.empty:
    st.warning(
        f"No season rows for this player in the sidebar window "
        f"({format_season_span(controls['seasons'])})."
    )
    st.stop()

if controls["era_z"] and not dst_view:
    all_seasons = season_stats_for_peer_analysis(
        conn, season=None, preset=preset_key, min_games=min_games
    )
    career = add_peer_z_era_column(career, all_seasons, min_games=min_games)

stat_cols = display_stats_for_positions([primary_pos])
career_cols = ["season", "teams", "games", "fantasy_points", "fp_per_game", "best_week", "best_week_fp"]
if "career_z" in career.columns:
    career_cols.append("career_z")
if "peer_z_era" in career.columns:
    career_cols.append("peer_z_era")
career_cols += [c for c in stat_cols if c in career.columns]

career_show = rename_stats_for_display(career[career_cols])
if "best_week_fp" in career.columns and "best_week_scoring" in career.columns:
    scoring_key = (
        career["best_week_scoring"].dropna().iloc[0]
        if career["best_week_scoring"].notna().any()
        else None
    )
    bw_label = best_week_fp_column_label(scoring_key)
    if "Best Week FP" in career_show.columns and bw_label not in career_show.columns:
        career_show = career_show.rename(columns={"Best Week FP": bw_label})

_render_career_window_section(
    career=career,
    career_show=career_show,
    career_cols=career_cols,
    entity_id=entity_id,
    primary_pos=primary_pos,
    dst_view=dst_view,
    conn=conn,
    preset_key=preset_key,
    min_games=min_games,
    controls=controls,
    stat_cols=stat_cols,
)

detail_season = _resolve_detail_season(_entity_seasons, window_years, controls)
if detail_season is not None:
    match = seasons_df[seasons_df["season"].astype(int) == detail_season]
    if not match.empty:
        _render_season_detail_section(
            conn=conn,
            entity_id=entity_id,
            detail_season=detail_season,
            season_row=match.iloc[0],
            career=career,
            dst_view=dst_view,
            preset_key=preset_key,
            min_games=min_games,
            primary_pos=primary_pos,
            stat_cols=stat_cols,
        )
