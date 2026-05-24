"""Fantasy Tracker — home page."""

from datetime import datetime

import streamlit as st

from app.components import get_db, render_sidebar
from src.db.connection import db_exists, get_ingest_summary
from src.db.queries import list_rankings_seasons, rankings_manifest_summary
from src.ui_text import title_case_ui

st.set_page_config(
    page_title="Fantasy Tracker",
    page_icon="🏈",
    layout="wide",
)

render_sidebar()

st.title("Fantasy Tracker")
st.markdown(
    "Explore **completed NFL regular seasons** with standard, half-PPR, and full PPR scoring. "
    "Use the sidebar to view one season, a range, or hand-picked years—then explore leaders, "
    "careers, and head-to-head comparisons."
)

st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("pages/1_Season_Leaders.py", label="Season Leaders", icon="📊")
    st.caption("Best players by season, position, and team filters.")
with col2:
    st.page_link("pages/2_Player_Profile.py", label="Player Profile", icon="👤")
    st.caption("Career breakdown, consistency, and Z-scores.")
with col3:
    st.page_link("pages/3_Compare.py", label="Compare Players", icon="⚖️")
    st.caption("All-time, window, or single-season head-to-head.")

st.divider()

st.subheader(title_case_ui("Database status"))
if db_exists():
    conn = get_db()
    summary = get_ingest_summary(conn) if conn is not None else get_ingest_summary()
    seasons = summary["seasons"]
    if seasons:
        span = f"{seasons[-1]}–{seasons[0]}" if len(seasons) > 1 else str(seasons[0])
        st.success(
            f"**{summary['season_count']}** seasons loaded ({span}). "
            f"Latest season: **{summary['latest_season']}**."
        )
        if summary.get("latest_ingested_at") is not None:
            ts = summary["latest_ingested_at"]
            if hasattr(ts, "strftime"):
                st.caption(f"Last ingest recorded: {ts.strftime('%Y-%m-%d %H:%M')}")
            else:
                st.caption(f"Last ingest recorded: {ts}")
        if summary.get("total_rows"):
            st.caption(f"Manifest row count (sum): {summary['total_rows']:,}")
        missing_hint = ""
        latest = seasons[0]
        if latest < datetime.now().year - 1:
            missing_hint = (
                f" Tip: if **{latest + 1}** or newer seasons are missing, run ingest after "
                "the regular season ends."
            )
        st.caption(
            f"Seasons: {', '.join(str(s) for s in sorted(seasons, reverse=True))}.{missing_hint}"
        )
        if conn is not None:
            rank_seasons = list_rankings_seasons(conn)
            manifest = rankings_manifest_summary(conn)
        else:
            rank_seasons = []
            manifest = None
        if rank_seasons:
            span = (
                f"{rank_seasons[0]}–{rank_seasons[-1]}"
                if len(rank_seasons) > 1
                else str(rank_seasons[0])
            )
            st.caption(
                f"Draft rankings (FantasyPros ECR): **{len(rank_seasons)}** seasons ({span}). "
                "Beat-draft-rank features only appear for those years."
            )
        elif manifest:
            st.caption("Draft rankings table is empty — re-run `scripts/ingest_rankings.py`.")
        else:
            st.caption(
                "No draft rankings loaded — run `scripts/ingest_rankings.py` for beat-draft-rank analysis."
            )
    else:
        st.info("Database exists but no seasons ingested yet.")
else:
    st.warning("No database at `data/fantasy_tracker.duckdb`. Run ingest to begin.")

st.divider()

st.subheader(title_case_ui("Getting started"))
st.code(
    ".\\.venv\\Scripts\\python.exe scripts\\ingest_season.py --season 2023\n"
    ".\\.venv\\Scripts\\python.exe -m streamlit run app/Home.py",
    language="powershell",
)

st.caption(
    "Share a profile: open a player, then copy the browser URL (includes `entity` and `season`). "
    "Data coverage: nflverse (~1999+). Regular season only."
)
