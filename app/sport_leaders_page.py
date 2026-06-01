"""Generic season leaders page for MLB / NBA / NHL."""

from __future__ import annotations

import streamlit as st

from app.components import get_db, render_sidebar
from app.leader_navigation import render_leaders_table
from app.surprise_ui import render_surprise_highlights
from src.analytics.metrics import add_fp_per_game
from src.analytics.peer_z_sport import enrich_leaders_dataframe_sport
from src.analytics.sport_surprise import (
    compute_sport_season_surprise_frame,
    enrich_leaders_with_surprise_sport,
    format_sport_surprise_caption,
)
from src.db.connection import db_exists
from src.db.queries import season_has_rankings
from src.season_selection import format_season_label, format_season_span, metric_window_caption
from src.sports.player_seasons import distinct_teams_for_seasons
from src.sports.registry import (
    default_leader_selection,
    get_sport,
    season_leaders,
    season_leaders_window,
)
from src.sports.display_stats import display_stats_for_leader_selection
from src.stats_columns import column_display_label, rename_stats_for_display
from src.ui_text import page_title_suffix, title_case_ui


def _coerce_leader_positions_list(
    sport_id: str, raw: object, prev: object
) -> list[str]:
    """Return a valid fantasy-position multiselect list (pure; no session writes)."""
    if sport_id == "mlb":
        from src.sports.mlb.positions import coerce_leader_selection

        return coerce_leader_selection(raw, prev)
    if sport_id == "nba":
        from src.sports.nba.positions import coerce_leader_selection

        return coerce_leader_selection(raw, prev)
    from src.sports.nhl.positions import coerce_leader_selection

    return coerce_leader_selection(raw, prev)


def _position_help(sport_id: str) -> str:
    if sport_id == "mlb":
        return (
            "Defaults to all hitter positions (C, 1B, 2B, …). Do not mix hitters and "
            "pitchers. **H** / **P** are shortcuts for the full hitter or pitcher groups. "
            "**DH** here means the stored *primary* position is DH (BRef `Pos` or MLB API) — "
            "not “played DH sometimes.” Most MLB DHs are stored as 1B/OF/LF; use **H** or "
            "several field tags instead of DH-only. Remove tags to narrow — empty clears the filter."
        )
    if sport_id == "nhl":
        return (
            "Defaults to all skater positions (C, LW, RW, D, F). Do not mix skaters and "
            "goalies. **S** selects all skaters; **G** is goalies only. Remove tags to "
            "narrow — empty clears the filter."
        )
    return (
        "Defaults to **all positions** (PG–C). Click the **×** on each tag to remove it "
        "and narrow the leaderboard."
    )


def render_sport_leaders_page(sport_id: str) -> None:
    meta = get_sport(sport_id)
    st.set_page_config(
        page_title=page_title_suffix(f"{meta.label} Season Leaders"),
        layout="wide",
    )
    from app.sport_context import init_sport_page

    init_sport_page(sport_id)
    controls = render_sidebar(sport=sport_id)
    st.title(title_case_ui("Season Leaders"))

    if not db_exists() or not controls["seasons"]:
        st.info(f"Ingest at least one {meta.label} season to use this page.")
        st.stop()

    conn = get_db()
    seasons = controls["seasons"]
    season = controls["season"]
    if season is None or not seasons:
        st.stop()

    is_window = controls["is_multi_season"]
    # Legacy key was used as multiselect key; Streamlit then forbids programmatic
    # writes on later reruns. Use a dedicated UI key and migrate once.
    legacy_pos_key = f"sport_leaders_positions_{sport_id}"
    ui_pos_key = f"{legacy_pos_key}_ui"
    prev_key = f"{legacy_pos_key}_prev"
    defaults_ver_key = f"{legacy_pos_key}_defaults_ver"
    defaults_ver = {"nba": 2, "mlb": 1, "nhl": 1}.get(sport_id)

    if ui_pos_key not in st.session_state:
        if legacy_pos_key in st.session_state:
            st.session_state[ui_pos_key] = list(st.session_state[legacy_pos_key])
        else:
            st.session_state[ui_pos_key] = list(default_leader_selection(sport_id))
        if defaults_ver is not None:
            st.session_state[defaults_ver_key] = defaults_ver
    elif defaults_ver is not None and st.session_state.get(defaults_ver_key, 0) < defaults_ver:
        current = list(st.session_state.get(ui_pos_key, []))
        legacy_default = {"nba": ["PG"], "mlb": ["H"], "nhl": ["S"]}.get(sport_id)
        if legacy_default and current == legacy_default:
            st.session_state[ui_pos_key] = list(default_leader_selection(sport_id))
            st.session_state[defaults_ver_key] = defaults_ver
    if prev_key not in st.session_state:
        st.session_state[prev_key] = list(st.session_state[ui_pos_key])

    def _on_positions_changed() -> None:
        r = list(st.session_state[ui_pos_key])
        p = st.session_state.get(prev_key, [])
        c = _coerce_leader_positions_list(sport_id, r, p)
        st.session_state[ui_pos_key] = c
        st.session_state[prev_key] = list(c)

    st.multiselect(
        title_case_ui("Position"),
        controls["fantasy_positions"],
        key=ui_pos_key,
        on_change=_on_positions_changed,
        help=_position_help(sport_id),
    )

    positions = list(st.session_state[ui_pos_key])
    if not positions:
        st.info("Select at least one position to view season leaders.")
        st.stop()

    if sport_id == "mlb" and positions == ["DH"]:
        st.caption(
            "Showing only rows stored as primary position **DH** (usually a small set). "
            "Players who mostly DH but are listed as 1B/OF on Baseball Reference are under "
            "those tags or under **H** (all hitter positions)."
        )

    if is_window:
        st.caption(
            f"**Window leaders** for **{format_season_span(seasons)}**: totals and FP/G sum each "
            f"qualified season (min **{controls['min_games']}** "
            f"{'PA' if sport_id == 'mlb' else 'games'} per season)."
        )
        cap = metric_window_caption(seasons)
        if cap:
            st.caption(cap)
        team_filter = None
    else:
        if sport_id == "mlb":
            st.caption(
                "Uses **ESPN** default fantasy points (v1). "
                "Hitters use **min plate appearances**; pitchers use **innings-pitched gates**."
            )
        else:
            st.caption("Uses **ESPN** default fantasy points (v1).")
        teams = ["All"] + distinct_teams_for_seasons(conn, sport_id, [int(season)])
        team_filter = st.selectbox(title_case_ui("Team"), teams)
        if sport_id in ("mlb", "nhl") and team_filter in (None, "All"):
            st.caption(
                "Mid-season trades appear as **one row per team** (stats for that stint only)."
            )
        elif sport_id == "nba" and team_filter in (None, "All"):
            st.caption(
                "Season totals are **one row per player** (all teams combined for that season)."
            )

    team_arg = (
        None
        if is_window or team_filter in (None, "All")
        else str(team_filter).strip()
    )

    if is_window:
        df = season_leaders_window(
            conn,
            sport_id,
            [int(y) for y in seasons],
            controls["preset_key"],
            positions=positions,
            min_games=controls["min_games"],
        )
    else:
        df = season_leaders(
            conn,
            sport_id,
            int(season),
            controls["preset_key"],
            positions=positions,
            min_games=controls["min_games"],
            team=team_arg,
        )

    if df.empty:
        vol_label = (
            "Min plate appearances"
            if sport_id == "mlb"
            else "Min games played"
        )
        st.warning(
            f"No results for these filters. Try lowering **{vol_label}** in the sidebar "
            "or adjusting the position filter."
        )
        st.stop()

    df = add_fp_per_game(df)
    surprise_all = None
    if not is_window:
        df = enrich_leaders_dataframe_sport(
            conn,
            sport_id,
            df,
            int(season),
            positions=positions,
            min_games=controls["min_games"],
            era_z=bool(controls.get("era_z")),
        )
    elif controls.get("era_z"):
        st.caption("Peer Z (era) is not shown for multi-season window leaders.")

    if not is_window and not season_has_rankings(conn, int(season), sport=sport_id):
        from app.sport_ingest_hints import no_rankings_message
        from src.rankings.fantasypros_limits import sport_draft_ecr_supported

        if sport_draft_ecr_supported(sport_id, int(season)):
            st.info(no_rankings_message(sport_id, int(season)))
        else:
            st.caption(no_rankings_message(sport_id, int(season)))
    if not is_window and season_has_rankings(conn, int(season), sport=sport_id):
        surprise_all = compute_sport_season_surprise_frame(
            conn,
            sport_id,
            int(season),
            controls["preset_key"],
            min_games=controls["min_games"],
        )
        if surprise_all is not None and not surprise_all.empty:
            df = enrich_leaders_with_surprise_sport(
                conn,
                sport_id,
                df,
                int(season),
                controls["preset_key"],
                min_games=controls["min_games"],
                surprise_df=surprise_all,
            )

    stat_cols = [
        c
        for c in display_stats_for_leader_selection(sport_id, positions)
        if c in df.columns
    ]
    display = [
        c
        for c in (
            "player_name",
            "position",
            "team",
            "seasons_in_window",
            "games",
            "fantasy_points",
            "fp_per_game",
            "peer_z_season",
            "peer_z_era",
        )
        if c in df.columns
    ]
    for col in ("draft_ecr", "finish_rank", "rank_delta"):
        if col in df.columns and col not in display:
            display.append(col)
    display += [c for c in stat_cols if c not in display]
    if "seasons_in_window" in display and not is_window:
        display = [c for c in display if c != "seasons_in_window"]

    if sport_id == "mlb":
        from src.sports.mlb.positions import is_hitter_only_selection, is_pitcher_only_selection

        if is_pitcher_only_selection(positions):
            st.caption("Pitching stats with ESPN scoring. Hitters and pitchers are not mixed.")
        elif is_hitter_only_selection(positions):
            st.caption("Hitting stats for selected field positions. Pick **P** or **SP**/**RP** for pitchers.")
    elif sport_id == "nhl":
        from src.sports.nhl.positions import is_goalie_only_selection, is_skater_only_selection

        if is_goalie_only_selection(positions):
            st.caption("Goalie stats only. Skaters and goalies are not mixed.")
        elif is_skater_only_selection(positions):
            st.caption("Skater stats for selected positions.")

    _sort_options: list[tuple[str, str]] = [
        (title_case_ui("FP per game"), "fp_per_game"),
        (title_case_ui("Fantasy points"), "fantasy_points"),
    ]
    if not is_window and "peer_z_season" in df.columns:
        _sort_options.append((title_case_ui("Peer Z (season)"), "peer_z_season"))
    if not is_window and controls.get("era_z") and "peer_z_era" in df.columns:
        _sort_options.append((title_case_ui("Peer Z (era)"), "peer_z_era"))
    if (
        not is_window
        and surprise_all is not None
        and not surprise_all.empty
        and "rank_delta" in df.columns
    ):
        _sort_options.append((column_display_label("rank_delta"), "rank_delta"))
    _sort_labels = [a for a, _ in _sort_options]
    _sort_map = dict(_sort_options)
    sort_by = st.selectbox(title_case_ui("Sort by"), _sort_labels, index=0)
    sort_col = _sort_map[sort_by]
    if sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=False, na_position="last")

    if surprise_all is not None and not surprise_all.empty:
        from src.sports.peer_positions import positions_for_peer_grouping

        expanded = [
            positions_for_peer_grouping(sport_id, p)
            for p in positions
            if positions_for_peer_grouping(sport_id, p) in surprise_all["position"].unique()
        ]
        if expanded:
            surprise_all = surprise_all[surprise_all["position"].isin(expanded)]
        with st.expander(title_case_ui("Winners & losers vs draft rank"), expanded=False):
            render_surprise_highlights(
                surprise_all,
                season=int(season),
                caption=format_sport_surprise_caption(sport_id),
            )

    name_col = title_case_ui("Player")
    table_df = df.reset_index(drop=True)
    link_season = int(season) if season is not None else int(seasons[0])
    if "player_id" in table_df.columns:
        shown = rename_stats_for_display(table_df[display])
        render_leaders_table(
            shown,
            entity_ids=table_df["player_id"],
            display_names=table_df["player_name"],
            season=link_season,
            name_column=name_col,
            sport_id=sport_id,
        )
        if is_window:
            st.caption("Profile links use the newest year in the sidebar window.")
    else:
        st.dataframe(
            rename_stats_for_display(table_df[display]),
            use_container_width=True,
            hide_index=True,
        )

    if stat_cols:
        with st.expander(title_case_ui("All stats"), expanded=False):
            extra = [c for c in display if c in table_df.columns]
            st.dataframe(
                rename_stats_for_display(table_df[extra]),
                use_container_width=True,
                hide_index=True,
            )

    csv_tag = format_season_label([int(s) for s in seasons]) if is_window else str(season)
    st.download_button(
        title_case_ui("Download CSV"),
        rename_stats_for_display(df).to_csv(index=False),
        file_name=f"{sport_id}_leaders_{csv_tag}.csv",
        mime="text/csv",
    )
