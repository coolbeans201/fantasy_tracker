"""Streamlit coverage summary for sport hub pages."""

from __future__ import annotations

import duckdb
import streamlit as st

from app.sport_ingest_hints import draft_ecr_ingest_command, gamelog_ingest_command
from src.rankings.fantasypros_limits import FP_SPORT_DRAFT_ECR_MIN_SEASON
from src.sports.data_coverage import sport_data_coverage
from src.sports.registry import SportMeta
from src.ui_text import title_case_ui


def render_sport_data_coverage(conn: duckdb.DuckDBPyConnection, meta: SportMeta) -> None:
    cov = sport_data_coverage(conn, meta.sport_id)
    st.subheader(title_case_ui("Data coverage"))

    if not cov["stats_seasons"]:
        st.warning("No season stats ingested yet.")
        return

    c1, c2, c3 = st.columns(3)
    stats_n = len(cov["stats_seasons"])
    gl_n = len(cov["gamelog_seasons"])
    ecr_n = len(cov["draft_ecr_ready_seasons"])
    c1.metric(title_case_ui("Season stats"), str(stats_n))
    c2.metric(title_case_ui("Game log seasons"), str(gl_n))
    c3.metric(
        title_case_ui("Draft ECR ready"),
        str(ecr_n),
        help="Seasons with enough matched FantasyPros draft rows for rank Δ UI",
    )

    latest = cov["latest_stats_season"]
    st.caption(
        f"Latest stats season: **{latest}**. "
        f"Game logs: {cov['gamelog_seasons'][:5]}{'…' if gl_n > 5 else ''}."
    )
    if cov["draft_ecr_ready_seasons"]:
        st.caption(
            "Draft ECR: "
            + ", ".join(str(y) for y in cov["draft_ecr_ready_seasons"][:8])
            + ("…" if ecr_n > 8 else "")
        )
    elif meta.sport_id in ("mlb", "nba", "nhl") and latest:
        st.caption(
            f"No draft ECR for recent seasons — one API call: "
            f"`{draft_ecr_ingest_command(meta.sport_id, int(latest))}`"
        )

    missing_gl = sorted(set(cov["stats_seasons"]) - set(cov["gamelog_seasons"]), reverse=True)
    if missing_gl and meta.sport_id in ("mlb", "nba", "nhl"):
        with st.expander(title_case_ui("Seasons missing game logs"), expanded=False):
            st.write(", ".join(str(y) for y in missing_gl[:12]))
            if latest:
                st.code(gamelog_ingest_command(meta.sport_id, int(latest)), language="powershell")

    unsupported = cov.get("draft_ecr_unsupported_seasons") or []
    if unsupported and meta.sport_id in ("mlb", "nba", "nhl"):
        st.caption(
            f"Draft ECR via FantasyPros is only available for seasons "
            f"**{FP_SPORT_DRAFT_ECR_MIN_SEASON}+** "
            f"({len(unsupported)} older stats season(s) in DB)."
        )

    if cov["stats_without_draft_ecr"] and meta.sport_id in ("mlb", "nba", "nhl"):
        with st.expander(title_case_ui("Stats seasons without draft ECR"), expanded=False):
            st.write(", ".join(str(y) for y in cov["stats_without_draft_ecr"][:12]))
            year = int(cov["stats_without_draft_ecr"][0])
            st.code(draft_ecr_ingest_command(meta.sport_id, year), language="powershell")

    with st.expander(title_case_ui("Getting started (3 steps)"), expanded=ecr_n == 0):
        st.markdown(
            f"1. **Season stats** — `{meta.ingest_command}`\n"
            f"2. **Game logs** (optional, slow) — "
            f"`{gamelog_ingest_command(meta.sport_id, int(latest or 2024))}`\n"
            f"3. **Draft ECR** (1 Public API call) — "
            f"`{draft_ecr_ingest_command(meta.sport_id, int(latest or 2024))}`"
        )
