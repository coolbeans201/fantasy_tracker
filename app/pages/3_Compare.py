"""Compare Players page."""



import numpy as np

import pandas as pd

import streamlit as st



from app.charts import dual_entity_season_chart

from app.components import fuzzy_player_select, get_db, render_sidebar

from app.consistency_ui import render_consistency_panel

from src.analytics.consistency import consistency_from_weekly, position_weekly_percentiles

from src.analytics.metrics import count_prime_seasons

from src.analytics.peer_z import peer_df_for_entity_season, peer_z_score

from src.analytics.variance import add_volume_flags, compute_career_z, load_thresholds

from src.db.connection import db_exists

from src.db.queries import (

    compare_entities,

    compare_shared_seasons,
    compare_union_seasons,

    entity_display_label,

    entity_seasons,

    entity_seasons_available,

    entity_weekly,

)

from src.positions import (

    COMPARE_GROUP_DST,

    COMPARE_GROUP_KICKER,

    COMPARE_GROUP_OFFENSE,

    DST_POSITION,

    compare_cohort,

    compare_cohorts_compatible,

    compare_incompatible_message,

    is_dst_position,

    normalize_fantasy_position,

)

from src.stats_columns import (

    build_stat_compare_frame,

    display_stats_for_positions,

    rename_compare_career_merge,

    rename_stats_for_display,

)

from src.ui_text import section_h3, title_case_ui


def _compare_season_scope_caption(seasons: list[int] | None) -> str | None:
    if not seasons:
        return None
    if len(seasons) == 1:
        return f"Season list: **{seasons[0]}** — a year at least one selection has data."
    return (
        f"Season list: any year either selection has data "
        f"(**{seasons[-1]}–{seasons[0]}**, {len(seasons)} seasons)."
    )


def _sync_compare_sidebar_seasons(
    entity_a: str,
    entity_b: str,
    sidebar_seasons: list[int],
    *,
    shared_seasons: list[int],
) -> None:
    """Scope sidebar seasons to the compare pair; rerun when the pair changes."""
    pair_key = f"{entity_a}|{entity_b}"
    st.session_state["compare_sidebar_seasons"] = sidebar_seasons
    st.session_state["compare_shared_seasons"] = shared_seasons

    if not sidebar_seasons:
        return

    if pair_key != st.session_state.get("compare_seasons_pair"):
        st.session_state["compare_seasons_pair"] = pair_key
        st.session_state["compare_season_default"] = max(sidebar_seasons)
        st.rerun()

    current = st.session_state.get("compare_season_default")
    if current not in sidebar_seasons:
        st.session_state["compare_season_default"] = max(sidebar_seasons)
        st.rerun()


st.set_page_config(page_title="Compare | Fantasy Tracker", layout="wide")



controls = render_sidebar(
    default_season=st.session_state.get("compare_season_default"),
    season_options=st.session_state.get("compare_sidebar_seasons"),
    season_scope_caption=_compare_season_scope_caption(
        st.session_state.get("compare_sidebar_seasons")
    ),
)

st.title("Compare Players")

st.caption(

    "QB, RB, WR, and TE can be compared to each other. "

    "Compare kickers to kickers and team defenses (DST) to other defenses only."

)



if not db_exists():

    st.info("Ingest at least one completed season to use this page.")

    st.stop()



conn = get_db()

min_games = controls["min_games"]

preset = controls["preset"]



col1, col2 = st.columns(2)

with col1:

    player_a = fuzzy_player_select("Player A", conn, key="compare_a")

with col2:

    player_b = fuzzy_player_select("Player B", conn, key="compare_b")



if not player_a or not player_b:

    st.stop()


_shared_seasons = compare_shared_seasons(conn, player_a, player_b, preset)
_union_seasons = compare_union_seasons(conn, player_a, player_b, preset)
_sync_compare_sidebar_seasons(
    player_a,
    player_b,
    _union_seasons,
    shared_seasons=_shared_seasons,
)

if not _union_seasons:
    st.warning("Neither selection has season data in the database for this scoring preset.")
    st.stop()


if "compare_mode" not in st.session_state:

    st.session_state.compare_mode = "All-time"



st.radio(

    "Compare mode",

    ["All-time", "Single season"],

    horizontal=True,

    key="compare_mode",

)

mode = str(st.session_state.compare_mode)

compare_season = (

    int(controls["season"]) if mode == "Single season" else None

)



if mode == "Single season" and compare_season is None:

    st.warning("Select a season in the sidebar.")

    st.stop()



if mode == "Single season":
    if not _shared_seasons:
        st.warning(
            "These selections have no seasons in common. Use **All-time** to compare "
            "players from different eras (career totals and side-by-side season rows)."
        )
        st.stop()
    if compare_season not in _shared_seasons:
        span = f"{_shared_seasons[-1]}–{_shared_seasons[0]}"
        st.warning(
            f"**{compare_season}** is not a year both played. "
            f"Overlapping seasons: **{span}** ({len(_shared_seasons)} years)."
        )
        st.stop()
    st.caption(
        f"Comparing the **{compare_season}** season — both selections played that year."
    )
else:
    st.caption(
        "All-time compares full careers (including different eras). "
        "Seasons only one player played still appear in the season-by-season table. "
        "Use **Single season** when you need the same calendar year for both."
    )
    if not _shared_seasons:
        st.info(
            "No overlapping seasons — all-time career compare still works; "
            "switch to **Single season** only if you want the same year for both."
        )



df_a, df_b = compare_entities(

    conn, player_a, player_b, preset, season=compare_season

)



if df_a.empty or df_b.empty:

    label_a = entity_display_label(conn, player_a)

    label_b = entity_display_label(conn, player_b)

    if mode == "Single season":

        if df_a.empty:

            st.warning(

                f"**{label_a}** has no stats for **{compare_season}** in the database."

            )

            avail = entity_seasons_available(conn, player_a, preset)

            if avail:

                st.caption(

                    f"{label_a} seasons available: {avail[0]}–{avail[-1]} "

                    f"({len(avail)} years ingested)."

                )

        if df_b.empty:

            st.warning(

                f"**{label_b}** has no stats for **{compare_season}** in the database."

            )

            avail = entity_seasons_available(conn, player_b, preset)

            if avail:

                st.caption(

                    f"{label_b} seasons available: {avail[0]}–{avail[-1]} "

                    f"({len(avail)} years ingested)."

                )

        st.info(

            "Single-season compare needs a regular-season row for **both** sides that year. "

            "Injured or inactive players often have no row (e.g. Andrew Luck did not play in 2017)."

        )

    else:

        st.warning("Insufficient data for one or both selections.")

    st.stop()



name_a = entity_display_label(conn, player_a)

name_b = entity_display_label(conn, player_b)



cohort_a = compare_cohort(player_a, df_a["position"].iloc[-1])

cohort_b = compare_cohort(player_b, df_b["position"].iloc[-1])

if not compare_cohorts_compatible(cohort_a, cohort_b):

    st.error(compare_incompatible_message(cohort_a, cohort_b))

    st.stop()





def _profile_position_key(position: str | None) -> str:

    if is_dst_position(position):

        return DST_POSITION

    return normalize_fantasy_position(position) or str(position)





def _compare_stat_positions(pos_a: str, pos_b: str) -> list[str]:

    if cohort_a == COMPARE_GROUP_DST:

        return [DST_POSITION]

    if cohort_a == COMPARE_GROUP_KICKER:

        return ["K"]

    return [_profile_position_key(pos_a), _profile_position_key(pos_b)]





def _consistency_panel_for_entity(
    label: str, entity_id: str, position: str, season: int
) -> None:
    weekly = entity_weekly(conn, entity_id, season, preset)
    if weekly.empty:
        st.info(f"{label}: no weekly data for {season}.")
        return
    p25, p75 = position_weekly_percentiles(conn, season, position, preset)
    metrics = consistency_from_weekly(weekly, p25=p25, p75=p75)
    render_consistency_panel(
        metrics,
        season=season,
        position_label=str(position),
        heading=f"{label} — weekly consistency ({season})",
    )





if mode == "All-time":

    total_a = df_a["fantasy_points"].sum()

    total_b = df_b["fantasy_points"].sum()

    games_a = int(df_a["games"].sum())

    games_b = int(df_b["games"].sum())

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(name_a, f"{total_a:.1f} FP (career)")

    m2.metric(name_b, f"{total_b:.1f} FP (career)")

    m3.metric("Difference", f"{total_a - total_b:+.1f}")

    m4.metric(

        "FP per game (career)",

        f"{total_a / games_a:.1f} vs {total_b / games_b:.1f}" if games_a and games_b else "—",

    )



    merged = df_a.merge(df_b, on="season", suffixes=("_a", "_b"), how="outer").sort_values(

        "season"

    )

    if not merged.empty:

        merged["diff"] = merged["fantasy_points_a"].fillna(0) - merged["fantasy_points_b"].fillna(0)

        merge_cols = ["season", "fantasy_points_a", "fantasy_points_b", "diff"]

        if cohort_a != COMPARE_GROUP_DST:

            merge_cols.extend(["teams_a", "teams_b"])

        st.markdown(section_h3("Season by season"))

        st.dataframe(

            rename_compare_career_merge(

                merged[merge_cols],

                name_a,

                name_b,

                include_teams=cohort_a != COMPARE_GROUP_DST,

            ),

            use_container_width=True,

            hide_index=True,

        )

        st.download_button(

            title_case_ui("Download compare CSV"),

            merged[merge_cols].to_csv(index=False),

            file_name=f"compare_{player_a}_{player_b}_alltime.csv",

            mime="text/csv",

            key="compare_alltime_csv",

        )

        st.markdown(section_h3("Fantasy points by season"))

        dual_entity_season_chart(merged, name_a, name_b)



    pos_a = df_a["position"].iloc[-1]

    pos_b = df_b["position"].iloc[-1]

    st.markdown(section_h3("Career stat totals"))

    stat_positions = _compare_stat_positions(pos_a, pos_b)

    stat_cols = list(dict.fromkeys(display_stats_for_positions(stat_positions)))

    totals_a = df_a[[c for c in stat_cols if c in df_a.columns]].sum(numeric_only=True)

    totals_b = df_b[[c for c in stat_cols if c in df_b.columns]].sum(numeric_only=True)

    stat_df = build_stat_compare_frame(totals_a, totals_b, name_a, name_b, stat_positions)

    if not stat_df.empty:

        st.dataframe(

            rename_stats_for_display(stat_df),

            use_container_width=True,

            hide_index=True,

        )



    career_a = compute_career_z(entity_seasons(conn, player_a, preset), min_games=min_games)

    career_b = compute_career_z(entity_seasons(conn, player_b, preset), min_games=min_games)

    ca = count_prime_seasons(career_a) if "career_z" in career_a.columns else 0

    cb = count_prime_seasons(career_b) if "career_z" in career_b.columns else 0

    st.caption(f"Prime seasons (career Z > 1): **{name_a}** {ca} · **{name_b}** {cb}")



else:

    row_a = df_a.iloc[0]

    row_b = df_b.iloc[0]

    games_a = int(row_a.get("games", 0) or 0)

    games_b = int(row_b.get("games", 0) or 0)

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(name_a, f"{row_a['fantasy_points']:.1f} FP")

    m2.metric(name_b, f"{row_b['fantasy_points']:.1f} FP")

    m3.metric("Difference", f"{row_a['fantasy_points'] - row_b['fantasy_points']:+.1f}")

    m4.metric(

        "FP per game",

        f"{row_a['fantasy_points'] / games_a:.1f} vs {row_b['fantasy_points'] / games_b:.1f}"

        if games_a and games_b

        else "—",

    )



    thresholds = load_thresholds()

    career_a = compute_career_z(entity_seasons(conn, player_a, preset), min_games=min_games)

    career_b = compute_career_z(entity_seasons(conn, player_b, preset), min_games=min_games)



    for label, row, eid, career in (

        (name_a, row_a, player_a, career_a),

        (name_b, row_b, player_b, career_b),

    ):

        peer_df = peer_df_for_entity_season(

            conn, compare_season, preset, row["position"], min_games

        )

        if cohort_a != COMPARE_GROUP_DST:

            peer_df = add_volume_flags(peer_df, min_games=min_games)

        z = peer_z_score(

            float(row["fantasy_points"]),

            peer_df,

            row["position"],

            min_peers=thresholds.get("min_qualified_peers", 10),

        )

        cz_row = career[career["season"].astype(int) == compare_season]

        cz_txt = ""

        if (

            not cz_row.empty

            and "career_z" in cz_row.columns

            and bool(cz_row["peer_qualified"].iloc[0])

            and not np.isnan(cz_row["career_z"].iloc[0])

        ):

            cz_txt = f" · career Z {cz_row['career_z'].iloc[0]:.2f}"

        peer_txt = f"{z:.2f}" if z is not None else "N/A"

        st.caption(f"**{label}** — peer Z (season) {peer_txt}{cz_txt}")



    st.markdown(section_h3("Weekly consistency"))
    col_a, col_b = st.columns(2)
    with col_a:
        _consistency_panel_for_entity(
            name_a, player_a, row_a["position"], compare_season
        )
    with col_b:
        _consistency_panel_for_entity(
            name_b, player_b, row_b["position"], compare_season
        )



    st.markdown(section_h3("Season stats"))

    stat_df = build_stat_compare_frame(

        row_a,

        row_b,

        name_a,

        name_b,

        _compare_stat_positions(row_a["position"], row_b["position"]),

    )

    if not stat_df.empty:

        st.dataframe(

            rename_stats_for_display(stat_df),

            use_container_width=True,

            hide_index=True,

        )

        st.download_button(

            title_case_ui("Download compare CSV"),

            stat_df.to_csv(index=False),

            file_name=f"compare_{player_a}_{player_b}_{compare_season}.csv",

            mime="text/csv",

            key="compare_season_csv",

        )


