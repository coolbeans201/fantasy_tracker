"""Shared Compare layout for MLB / NBA / NHL with career-scoped sidebar seasons."""

from __future__ import annotations

from collections.abc import Callable

import duckdb
import pandas as pd
import streamlit as st

from app.charts import dual_entity_season_chart
from app.components import get_db, render_sidebar
from app.sport_context import init_sport_page
from app.sport_profile_entry import player_id_from_profile_link
from app.sport_season_scope import compare_season_scope_caption, sync_compare_sidebar_seasons
from src.analytics.metrics import add_fp_per_game
from src.analytics.peer_z_sport import peer_df_for_entity_season_sport, peer_z_score_sport
from src.analytics.sport_surprise import season_surprise_for_entity_sport
from src.analytics.sport_variance import add_volume_flags_sport, compute_career_z_sport
from src.db.connection import db_exists
from src.db.queries import season_has_rankings
from src.season_selection import format_season_span
from src.sports.compare_cohort import (
    compare_cohorts_compatible,
    mlb_compare_cohort_hint_from_label,
    nhl_compare_cohort_hint_from_label,
    prepare_compare_season_rows,
)
from src.sports.display_stats import display_stats_for_leader_selection
from src.sports.player_career import compare_player_seasons
from src.sports.player_seasons import compare_shared_seasons, compare_union_seasons
from src.stats_columns import rename_stats_for_display
from src.ui_text import page_title_suffix, section_h3, title_case_ui

RowLoader = Callable[[duckdb.DuckDBPyConnection, int], pd.DataFrame]

_COMPARE_MODES = ("All-time", "Single season", "Selected seasons")


def _pick_players(
    conn: duckdb.DuckDBPyConnection,
    sport_id: str,
    *,
    load_rows: RowLoader | None,
    season: int,
) -> tuple[str, str, str, str] | None:
    """Return player_id_a, player_id_b, name_a, name_b or None if stopped."""
    if load_rows is not None:
        rows = load_rows(conn, season)
        if rows.empty:
            st.warning("No players for this season and filter.")
            st.stop()
        names = rows["player_name"].tolist()
        id_by_name = dict(zip(rows["player_name"], rows["player_id"].astype(str)))
        col1, col2 = st.columns(2)
        with col1:
            name_a = st.selectbox(title_case_ui("Player A"), names, key=f"compare_a_{sport_id}")
        with col2:
            name_b = st.selectbox(title_case_ui("Player B"), names, key=f"compare_b_{sport_id}")
        return id_by_name[name_a], id_by_name[name_b], name_a, name_b

    col1, col2 = st.columns(2)
    with col1:
        st.caption("Player A")
        pid_a, _, name_a = player_id_from_profile_link(
            conn,
            stats_table=_stats_table(sport_id),
            search_players=_search_fn(sport_id),
            sidebar_season=season,
            stop_if_incomplete=False,
        )
    with col2:
        st.caption("Player B")
        pid_b, _, name_b = player_id_from_profile_link(
            conn,
            stats_table=_stats_table(sport_id),
            search_players=_search_fn(sport_id),
            sidebar_season=season,
            stop_if_incomplete=False,
        )
    if not pid_a or not pid_b:
        return None
    return pid_a, pid_b, name_a or pid_a, name_b or pid_b


def _stats_table(sport_id: str) -> str:
    from src.sports.player_seasons import stats_table

    return stats_table(sport_id)


def _search_fn(sport_id: str):
    if sport_id == "mlb":
        from src.sports.mlb.queries import search_players

        return search_players
    if sport_id == "nba":
        from src.sports.nba.queries import search_players

        return search_players
    from src.sports.nhl.queries import search_players

    return search_players


def render_sport_compare_page(
    sport_id: str,
    *,
    label: str,
    caption: str | None = None,
    load_rows: RowLoader | None = None,
    use_search_pickers: bool = False,
) -> None:
    st.set_page_config(page_title=page_title_suffix(f"{label} Compare"), layout="wide")
    init_sport_page(sport_id)

    controls = render_sidebar(
        sport=sport_id,
        default_season=st.session_state.get(f"compare_season_default_{sport_id}"),
        season_options=st.session_state.get(f"compare_sidebar_seasons_{sport_id}"),
        season_scope_caption=compare_season_scope_caption(
            st.session_state.get(f"compare_sidebar_seasons_{sport_id}"),
            shared_seasons=st.session_state.get(f"compare_shared_seasons_{sport_id}"),
        ),
    )
    st.title(title_case_ui("Compare Players"))
    if caption:
        st.caption(caption)

    if sport_id == "mlb":
        st.radio(
            title_case_ui("Cohort"),
            ["Hitters", "Pitchers"],
            horizontal=True,
            key="mlb_compare_cohort",
        )
    elif sport_id == "nhl":
        st.radio(
            title_case_ui("Cohort"),
            ["Skaters", "Goalies"],
            horizontal=True,
            key="nhl_compare_cohort",
        )

    if not db_exists() or not controls["seasons"]:
        st.info(f"Ingest {label} data first.")
        st.stop()

    conn = get_db()
    min_games = controls["min_games"]

    if f"compare_mode_{sport_id}" not in st.session_state:
        st.session_state[f"compare_mode_{sport_id}"] = "All-time"
    st.radio(
        title_case_ui("Compare mode"),
        list(_COMPARE_MODES),
        format_func=title_case_ui,
        horizontal=True,
        key=f"compare_mode_{sport_id}",
    )
    mode = str(st.session_state[f"compare_mode_{sport_id}"])
    if mode not in _COMPARE_MODES:
        mode = _COMPARE_MODES[0]

    if mode == "Selected seasons" and not controls["is_multi_season"]:
        st.caption(
            f"**Selected seasons** uses the sidebar year (**{controls['season']}**). "
            "Set sidebar **Season view** to **Season range** or **Pick seasons** for a window."
        )
    elif mode == "Selected seasons":
        st.caption(
            f"**Selected seasons** compares over **{format_season_span(controls['seasons'])}**."
        )
    else:
        st.caption(
            "**All-time** = full careers · **Single season** = same calendar year · "
            "**Selected seasons** = sidebar window."
        )

    pick_season = int(controls["season"]) if mode == "Single season" else None
    pick_window = list(controls["seasons"]) if mode == "Selected seasons" else None
    picker_season = pick_season if pick_season is not None else int(controls["season"])

    if use_search_pickers or load_rows is None:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**{title_case_ui('Player A')}**")
            player_a, _, name_a = player_id_from_profile_link(
                conn,
                stats_table=_stats_table(sport_id),
                search_players=_search_fn(sport_id),
                sidebar_season=picker_season,
                key_suffix="_cmp_a",
                stop_if_incomplete=False,
            )
        with col2:
            st.markdown(f"**{title_case_ui('Player B')}**")
            player_b, _, name_b = player_id_from_profile_link(
                conn,
                stats_table=_stats_table(sport_id),
                search_players=_search_fn(sport_id),
                sidebar_season=picker_season,
                key_suffix="_cmp_b",
                stop_if_incomplete=False,
            )
        if not player_a or not player_b:
            missing = []
            if not player_a:
                missing.append(title_case_ui("Player A"))
            if not player_b:
                missing.append(title_case_ui("Player B"))
            st.info(f"Select {' and '.join(missing)} to compare.")
            st.stop()
        name_a = name_a or player_a
        name_b = name_b or player_b
    else:
        picked = _pick_players(conn, sport_id, load_rows=load_rows, season=picker_season)
        if picked is None:
            st.stop()
        player_a, player_b, name_a, name_b = picked

    shared = compare_shared_seasons(conn, sport_id, player_a, player_b)
    union = compare_union_seasons(conn, sport_id, player_a, player_b)
    sync_compare_sidebar_seasons(
        sport_id, player_a, player_b, union, shared_seasons=shared
    )

    if not union:
        st.warning("Neither player has season data in the database.")
        st.stop()

    cohort_hint: str | None = None
    if sport_id == "mlb":
        cohort_hint = mlb_compare_cohort_hint_from_label(
            st.session_state.get("mlb_compare_cohort")
        )
    elif sport_id == "nhl":
        cohort_hint = nhl_compare_cohort_hint_from_label(
            st.session_state.get("nhl_compare_cohort")
        )

    pos_a = conn.execute(
        f"SELECT position FROM {_stats_table(sport_id)} WHERE player_id = ? ORDER BY season DESC LIMIT 1",
        [player_a],
    ).fetchone()
    pos_b = conn.execute(
        f"SELECT position FROM {_stats_table(sport_id)} WHERE player_id = ? ORDER BY season DESC LIMIT 1",
        [player_b],
    ).fetchone()
    ok, msg = compare_cohorts_compatible(
        sport_id,
        pos_a[0] if pos_a else None,
        pos_b[0] if pos_b else None,
        conn=conn,
        player_a=player_a,
        player_b=player_b,
        season=pick_season,
        seasons=pick_window,
        cohort_hint=cohort_hint,
    )
    if not ok and msg:
        st.warning(msg)
        st.stop()

    if mode == "Single season":
        if not shared:
            st.warning("These players have no seasons in common. Try **All-time**.")
            st.stop()
        if pick_season not in shared:
            span = f"{shared[-1]}–{shared[0]}"
            st.warning(
                f"**{pick_season}** is not a year both played. Overlap: **{span}**."
            )
            st.stop()

    df_a, df_b = compare_player_seasons(
        conn,
        sport_id,
        player_a,
        player_b,
        season=pick_season,
        seasons=pick_window,
    )
    df_a = prepare_compare_season_rows(df_a, sport_id, cohort_hint=cohort_hint)
    df_b = prepare_compare_season_rows(df_b, sport_id, cohort_hint=cohort_hint)
    if not df_a.empty:
        df_a = compute_career_z_sport(add_fp_per_game(df_a), sport_id)
    if not df_b.empty:
        df_b = compute_career_z_sport(add_fp_per_game(df_b), sport_id)

    if df_a.empty and df_b.empty:
        st.warning("No rows for this compare mode.")
        st.stop()

    def _compare_table_columns(frame: pd.DataFrame) -> list[str]:
        base = [
            "season",
            "team",
            "position",
            "games",
            "fantasy_points",
            "fp_per_game",
            "career_z",
        ]
        positions_for_stats: list[str] | None = None
        if sport_id == "mlb" and cohort_hint:
            from src.sports.mlb.positions import (
                COMPARE_GROUP_HITTER,
                COMPARE_GROUP_PITCHER,
                FIELD_POSITIONS,
                PITCHER_POSITIONS,
            )

            positions_for_stats = (
                list(PITCHER_POSITIONS)
                if cohort_hint == COMPARE_GROUP_PITCHER
                else list(FIELD_POSITIONS)
            )
        elif sport_id == "nhl" and cohort_hint:
            from src.sports.nhl.positions import (
                COMPARE_GROUP_GOALIE,
                COMPARE_GROUP_SKATER,
                GOALIE_POSITION,
                SKATER_POSITIONS,
            )

            positions_for_stats = (
                [GOALIE_POSITION]
                if cohort_hint == COMPARE_GROUP_GOALIE
                else list(SKATER_POSITIONS)
            )
        stat_cols = display_stats_for_leader_selection(sport_id, positions_for_stats)
        cols = [c for c in base if c in frame.columns]
        cols += [c for c in stat_cols if c in frame.columns and c not in cols]
        return cols

    st.markdown(section_h3("Season by season"))
    a_show = rename_stats_for_display(df_a[_compare_table_columns(df_a)])
    b_show = rename_stats_for_display(df_b[_compare_table_columns(df_b)])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{name_a}**")
        st.dataframe(a_show, use_container_width=True, hide_index=True)
    with c2:
        st.markdown(f"**{name_b}**")
        st.dataframe(b_show, use_container_width=True, hide_index=True)

    if mode == "Single season" and pick_season is not None:
        ra = df_a[df_a["season"].astype(int) == pick_season]
        rb = df_b[df_b["season"].astype(int) == pick_season]
        if not ra.empty and not rb.empty:
            fp_a = float(ra["fantasy_points"].iloc[0])
            fp_b = float(rb["fantasy_points"].iloc[0])
            peer_df = peer_df_for_entity_season_sport(conn, sport_id, pick_season, min_games)
            peer_df = add_volume_flags_sport(peer_df, sport_id, min_games=min_games)
            pz_a = peer_z_score_sport(fp_a, peer_df, sport_id, ra["position"].iloc[0])
            pz_b = peer_z_score_sport(fp_b, peer_df, sport_id, rb["position"].iloc[0])
            m1, m2, m3, m4 = st.columns(4)
            m1.metric(name_a, f"{fp_a:.1f} FP")
            m2.metric(name_b, f"{fp_b:.1f} FP")
            m3.metric(title_case_ui("Difference"), f"{fp_a - fp_b:+.1f}")
            m4.metric(
                title_case_ui("Peer Z"),
                f"{pz_a:+.2f} vs {pz_b:+.2f}" if pz_a is not None and pz_b is not None else "—",
            )
            if season_has_rankings(conn, pick_season, sport=sport_id):
                for label, eid, row in (
                    (name_a, player_a, ra),
                    (name_b, player_b, rb),
                ):
                    surprise = season_surprise_for_entity_sport(
                        conn,
                        sport_id,
                        eid,
                        pick_season,
                        controls["preset_key"],
                        min_games=min_games,
                        position=row["position"].iloc[0],
                    )
                    if surprise:
                        st.caption(
                            f"**{label}** — draft ECR {surprise['draft_ecr']}, "
                            f"finish {surprise['finish_rank']}, "
                            f"rank Δ {surprise['rank_delta']:+d}"
                        )

    st.markdown(section_h3("Fantasy points by season"))
    merged = df_a.merge(df_b, on="season", suffixes=("_a", "_b"), how="outer").sort_values(
        "season"
    )
    if not merged.empty:
        dual_entity_season_chart(merged, name_a, name_b)

    if not df_a.empty and not df_b.empty:
        st.markdown(section_h3("Career totals (window)"))
        totals_a = df_a[["fantasy_points", "games"]].sum()
        totals_b = df_b[["fantasy_points", "games"]].sum()
        t1, t2, t3 = st.columns(3)
        t1.metric(f"{name_a} FP", f"{totals_a['fantasy_points']:.1f}")
        t2.metric(f"{name_b} FP", f"{totals_b['fantasy_points']:.1f}")
        t3.metric(title_case_ui("FP difference"), f"{totals_a['fantasy_points'] - totals_b['fantasy_points']:+.1f}")

    st.download_button(
        title_case_ui("Download compare CSV"),
        pd.concat(
            [
                df_a.assign(player=name_a),
                df_b.assign(player=name_b),
            ],
            ignore_index=True,
        )
        .pipe(lambda d: rename_stats_for_display(d))
        .to_csv(index=False),
        file_name=f"{sport_id}_compare.csv",
        mime="text/csv",
    )
