# Fantasy Tracker

Open-source fantasy analytics for **completed seasons** — season leaders, player profiles, head-to-head compare, and Z-scores vs peers and career baselines.

**Sports:** **NFL** (full weekly + career), **MLB**, **NBA**, and **NHL** (season-level stats and ESPN-style fantasy points per sport). Inspired by [NFL Perry](https://www.nflperry.com/) for NFL use cases; focused on historical analysis (not gameplay).

## Features

### NFL

- **Scoring:** Standard, Half-PPR, Full PPR for offense; **custom offense presets** (sidebar editor, no re-ingest); **ESPN default** for kickers and team **D/ST**
- **D/ST:** Sacks, turnovers, TDs, **points allowed** (from game schedules), **yards allowed** (opponent pass + rush from nflverse team stats), ESPN PA/yards tier bonuses
- **Season window (sidebar):** **Single season**, **season range**, or **pick seasons** — drives Leaders, Profile, and Compare
- **Season Leaders:** QB/RB/WR/TE/K plus **DST**; sortable FP/G; **window leaders** when multiple years are selected; clickable names → Profile
- **Player Profile:** **Career & window** (season table, peak/prime, career chart) and **season detail** (peer Z, consistency, weekly opponent, boom/bust weeks)
- **Compare:** **All-time**, **single season** (same year for both), or **selected seasons** (sidebar window; cross-era OK)
- **Variance:** Peer Z (season), optional peer Z (era), career Z; volume gates in [`src/analytics/thresholds.yaml`](src/analytics/thresholds.yaml)
- **Expectations:** FantasyPros draft ECR vs finish rank (winners/losers); weekly ECR on Profile when rankings are ingested

### MLB · NBA · NHL

- Per-sport hub: **Overview**, **Season Leaders**, **Player Profile**, **Compare** (under `app/pages/{mlb,nba,nhl}/`)
- **MLB:** Field positions (**C, 1B, 2B, 3B, SS, LF, CF, RF, OF, DH**) and **SP/RP**; ESPN-style season FP; BRef stats + BRef/FanGraphs position lookup
- **NBA:** Game-log season aggregates, positions from `PlayerIndex`, Half-PPR-style FP
- **NHL:** Skater positions (**C, LW, RW, D, F**) and **G** for goalies; season FP from nhlpy (`positionCode`)

### App

- **Multi-sport home:** `st.navigation` + nested pages (Streamlit **1.36+**)
- **Repair database** (sidebar): NFL games played, player index, display names, weekly **opponent**, D/ST **points/yards allowed**, MLB **accented player names**, NBA **positions from team rosters**

## Data

| Sport | Source | Notes |
|-------|--------|--------|
| **NFL** | [nflverse](https://github.com/nflverse) via [`nflreadpy`](https://nflreadpy.nflverse.com/) | 1999+ REG only; QB/RB/WR/TE/K + team D/ST |
| **MLB** | [pybaseball](https://github.com/jldbc/pybaseball) (BRef / FanGraphs) | BRef from **2008**; bulk uses `--source bref` |
| **NBA** | [nba_api](https://github.com/swar/nba_api) | Season game logs; bulk from ~2000 |
| **NHL** | [nhl-api-py](https://github.com/coreyjs/nhl-api-py) | nhlpy v3 seasons; bulk from ~2005 |
| **Rankings** | nflverse FantasyPros ECR | NFL draft + weekly (optional) |

NFL weekly rows include **opponent** (`opponent_team`). D/ST **points allowed** are not in nflverse team box scores — we join **schedules** (`home_score` / `away_score`). **Yards allowed** = opponent **passing + rushing** yards in the same game.

After schema or ingest-logic changes, **re-ingest** affected seasons and/or run sidebar **Repair database**.

## Quick start

**Python 3.12+**, **64-bit** recommended. Always use the **venv interpreter** (system `python` often lacks `nflreadpy`):

```powershell
cd fantasy-tracker
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps

# Verify environment
.\.venv\Scripts\python.exe scripts\check_env.py

# NFL (required before NFL pages show data)
.\.venv\Scripts\python.exe scripts\ingest_season.py --season 2023
# Or full NFL history:
.\.venv\Scripts\python.exe scripts\ingest_season.py --bulk --from-year 1999 --to-year 2025

# Other sports (same venv; see Commands for bulk ranges)
.\.venv\Scripts\python.exe scripts\ingest_mlb.py --bulk --from-year 2008 --to-year 2025 --source bref
.\.venv\Scripts\python.exe scripts\ingest_nba.py --bulk --from-year 2000 --to-year 2025
.\.venv\Scripts\python.exe scripts\ingest_nhl.py --bulk --from-year 2005 --to-year 2025

# Or unified wrapper:
.\.venv\Scripts\python.exe scripts\ingest.py --sport nfl --season 2023
.\.venv\Scripts\python.exe scripts\ingest.py --sport mlb --season 2024 --source bref

# Draft / weekly expert ranks (NFL beat-draft-rank analysis):
.\.venv\Scripts\python.exe scripts\ingest_rankings.py

# Run app → http://localhost:8501
.\.venv\Scripts\python.exe -m streamlit run app/Home.py
```

Database: `data/fantasy_tracker.duckdb` (gitignored).

**Sidebar:** scoring preset (NFL offense: built-ins or saved **★ custom** presets), **Custom scoring presets** expander, **season view** (single / range / pick), min games, optional peer Z (era). **Repair database** runs maintenance backfills (see Features).

**Custom scoring (v1):** NFL offense only (QB/RB/WR/TE). Points are computed at query time from weekly/season stat columns. Built-in presets still use precomputed `fantasy_points_*` from ingest. See [docs/CUSTOM_SCORING.md](docs/CUSTOM_SCORING.md).

## What you can do

| Question | Where |
|----------|--------|
| Who were the top half-PPR RBs in 2022 with at least 8 games? | **NFL → Season Leaders** — single season 2022, RB, Half-PPR |
| Match my league’s reception scoring (e.g. 1.25 PPR) | Sidebar **Custom scoring presets** — clone Full PPR, tweak, save, select **★** |
| Who dominated 2018–2022 on total points and per game? | **Season Leaders** — **season range** 2018–2022 |
| How does a player’s 2021 compare to their own career? | **Player Profile** — **Career Z** in **Career & window** |
| How elite was a season vs peers that year? | **Player Profile** → **Season detail** — **Peer Z (season)** |
| Did he beat or miss his draft rank? | **NFL Season Leaders** — ingest rankings; **Winners & losers** / **Rank Δ** |
| Compare two players in one NFL season | **Compare** — **Single season**; same sidebar year |
| Compare careers across eras | **Compare** — **All-time** or **Selected seasons** |
| Top defenses or kickers (ESPN scoring) | **NFL Season Leaders** — **DST** or **K** |
| MLB/NBA/NHL season leaders | Sport hub → **Season Leaders** |
| Open a leader in full profile | Click **Player** name on Season Leaders (NFL, MLB, NBA, NHL) |
| Share a profile link | **Player Profile** — URL `?entity=` / `?season=` |
| Tune peer Z volume gates | `scripts/volume_report.py --season 2023` |

## Compare modes (NFL)

| Mode | Use when |
|------|----------|
| **All-time** | Full careers in the database |
| **Single season** | Same calendar year for both players (must overlap) |
| **Selected seasons** | Stats limited to the sidebar season window |

For multi-year compare, set sidebar **Season view** to **Season range** or **Pick seasons**, then choose **Selected seasons**.

## Commands

| Script | Purpose |
|--------|---------|
| `scripts/ingest.py` | Unified ingest (`--sport nfl\|mlb\|nba\|nhl`, `--season`, `--bulk`) |
| `scripts/ingest_season.py` | NFL (`--season`, `--bulk --from-year 1999 --to-year 2025`) |
| `scripts/ingest_mlb.py` | MLB (`--season`, `--bulk`; `--source auto\|bref\|fangraphs`; `--fail-fast`) |
| `scripts/ingest_nba.py` | NBA (`--bulk --from-year 2000` typical) |
| `scripts/ingest_nhl.py` | NHL (`--bulk --from-year 2005` typical) |
| `scripts/ingest_rankings.py` | FantasyPros ECR (NFL) from nflverse |
| `scripts/rankings_coverage.py` | Draft ECR vs stats ingest coverage |
| `scripts/volume_report.py` | Peer-Z volume gate check (`--season 2023`) |
| `scripts/rebuild_players.py` | Rebuild NFL player search index |
| `scripts/check_env.py` | Python arch, packages, DB presence |

Resume a failed bulk ingest from a year:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_season.py --bulk --from-year 2001 --to-year 2025
.\.venv\Scripts\python.exe scripts\ingest_mlb.py --season 2024 --source bref
```

**Maintenance from CLI** (same as sidebar Repair database):

```powershell
.\.venv\Scripts\python.exe -c "from src.db.connection import get_connection, init_schema; from src.db.maintenance import backfill_dst_points_allowed, backfill_mlb_player_names, backfill_weekly_opponents, recompute_games_played, rebuild_players_table, refresh_player_display_names; init_schema(); c=get_connection(); recompute_games_played(c); rebuild_players_table(c); refresh_player_display_names(c); backfill_weekly_opponents(c); backfill_dst_points_allowed(c); backfill_mlb_player_names(c); c.close()"
```

## Configuration

| File | What it controls |
|------|------------------|
| [`src/scoring/presets.yaml`](src/scoring/presets.yaml) | Built-in NFL offense (Standard / Half-PPR / Full PPR) |
| `scoring_presets` table (DuckDB) | Saved custom NFL offense presets |
| [`src/scoring/kicker_presets.yaml`](src/scoring/kicker_presets.yaml) | ESPN kicker scoring |
| [`src/scoring/dst_presets.yaml`](src/scoring/dst_presets.yaml) | ESPN D/ST (events + PA + yards tiers) |
| [`config/settings.yaml`](config/settings.yaml) | Default min games (8) |
| [`src/analytics/thresholds.yaml`](src/analytics/thresholds.yaml) | Volume gates for peer Z |
| [`.streamlit/config.toml`](.streamlit/config.toml) | Theme; `fileWatcherType = none` |

Re-ingest after schema, position-filter, or D/ST/MLB ingest logic changes.

## Project layout

```
app/                    Streamlit: Home.py + navigation.py + pages/{nfl,mlb,nba,nhl}/
src/sports/             Per-sport plugins (registry, positions, queries, scoring)
src/team_dst_columns.py NFL D/ST mapping, PA/yards from schedules + team stats
src/text_encoding.py    Unicode repair for scraped names (MLB, etc.)
src/season_selection.py Sidebar season window helpers
src/scoring/            Presets, custom store, query-time FP SQL
src/analytics/          Z-scores, consistency, surprise vs ECR
src/db/                 DuckDB schema, queries, maintenance backfills
scripts/                Ingest and utilities
docs/                   Roadmaps and design notes
data/                   Local DuckDB (gitignored)
```

Docs: [docs/ENHANCEMENT_ROADMAP.md](docs/ENHANCEMENT_ROADMAP.md), [docs/CUSTOM_SCORING.md](docs/CUSTOM_SCORING.md), [docs/MULTISPORT_ROADMAP.md](docs/MULTISPORT_ROADMAP.md).

## Troubleshooting

Run `.\.venv\Scripts\python.exe scripts\check_env.py` first.

| Issue | What to do |
|-------|------------|
| `ModuleNotFoundError: nflreadpy` | Use `.\.venv\Scripts\python.exe`, not bare `python`; run `pip install -r requirements.txt` |
| `python` not found / Store opens | Install 64-bit Python; use `py -3.12`; disable App execution aliases |
| pandas build / Meson errors | **32-bit Python** — recreate venv (64-bit) and reinstall requirements |
| `Activate.ps1` blocked | Skip activation; use `.\.venv\Scripts\python.exe` for all commands |
| Empty Season Leaders | Lower min games; re-ingest; **Repair database** |
| D/ST **points/yards allowed** all zero | **Repair database** or re-ingest NFL; PA needs schedules, yards need team stats |
| MLB names like `Jos\xc3\xa9` | **Repair database** or re-ingest MLB (`src/text_encoding.py` fixes on read + backfill) |
| MLB positions all **H** / **P** | Re-ingest MLB; new ingests store **CF, 1B, SP, RP**, etc. (legacy H/P still filter in UI) |
| Missing **Opponent** (NFL weekly) | **Repair database** or re-ingest that season |
| Player not in search | Type 2+ letters; **Repair database** or `scripts/rebuild_players.py` |
| MLB BRef bulk skips seasons | Retry with `--season YEAR --source bref`; use `--fail-fast` to stop on first error |
| NBA everyone shows **SF** | **Repair database** or re-ingest; positions come from **team rosters** (PlayerIndex join uses normalized player IDs) |
| NHL partial seasons | nhlpy caps page size; re-ingest affected years with current `ingest_nhl.py` |
| NHL positions all **S** / **G** | Re-ingest NHL; new ingests store **C, LW, RW, D** and **G** (legacy S still filters as skaters) |
| Streamlit nested pages / duplicate URLs | Requires Streamlit **≥1.36**; entrypoint is `app/Home.py` |
| Custom preset not on pages | Save preset, select **★** in **Scoring** |

Expected NFL ingest: `Dropped N weekly rows` (non-skill positions). Bulk ingest is **one season at a time** — safe to resume mid-range.

## License

MIT — see [LICENSE](LICENSE). NFL data via nflverse is CC-BY 4.0. Respect terms for pybaseball, nba_api, and NHL API sources when redistributing data.

## Contributing

PRs welcome. Before submitting:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
```
