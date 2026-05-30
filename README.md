# Fantasy Tracker

Open-source fantasy analytics for **completed seasons** — season leaders, player profiles, head-to-head compare, and Z-scores vs peers and career baselines.

**Sports:** **NFL** (full weekly + career), **MLB**, **NBA**, and **NHL** (season-level stats and ESPN-style fantasy points per sport). Inspired by [NFL Perry](https://www.nflperry.com/) for NFL use cases; focused on historical analysis (not gameplay).

## Features

### NFL

- **Scoring:** Standard, Half-PPR, Full PPR for offense; **custom offense presets** (sidebar editor, no re-ingest); **ESPN default** for kickers and team **D/ST**
- **D/ST:** Sacks, turnovers, TDs, **points allowed** (from game schedules), **yards allowed** (opponent pass + rush from nflverse team stats), ESPN PA/yards tier bonuses
- **Season window (sidebar):** **Single season**, **season range**, or **pick seasons** — drives Leaders, Profile, and Compare
- **Season Leaders:** QB/RB/WR/TE/K plus **DST** (default offense only; **K**/**DST** exclusive views); sortable FP/G; **window leaders** when multiple years are selected; draft-rank surprise when rankings ingested; clickable names → Profile
- **Player Profile:** **Career & window** (season table, peak/prime, career chart) and **season detail** (peer Z, consistency, weekly opponent, boom/bust weeks)
- **Compare:** **All-time**, **single season** (same year for both), or **selected seasons** (sidebar window; cross-era OK)
- **Variance:** Peer Z (season), optional peer Z (era), career Z; volume gates in [`src/analytics/thresholds.yaml`](src/analytics/thresholds.yaml)
- **Expectations:** FantasyPros draft ECR vs finish rank (winners/losers) on MLB/NBA/NHL leaders; NFL weekly ECR + consistency on Profile when nflverse rankings are ingested

### MLB · NBA · NHL

- Per-sport hub: **Overview**, **Season Leaders**, **Player Profile**, **Compare** (under `app/pages/{mlb,nba,nhl}/`)
- **Season window (sidebar):** Same **single / range / pick** modes as NFL for leaders, profile, and compare
- **Season Leaders:** Position-aware stat columns; **draft ECR vs finish rank** (winners/losers) when FantasyPros data is ingested; clickable **Player** → profile (`?entity=` / `?season=`); optional peer Z (season + era); **All stats** expander on the table
- **Player Profile:** Career/window table, peak/prime highlights, season detail, game logs where ingested; **no internal `player_id` in tables**
- **Compare:** **All-time**, **single season**, or **selected seasons**; **Skaters vs goalies** (NHL) and **Hitters vs pitchers** (MLB) cohort pickers — cross-cohort compare is blocked
- **MLB:** Season Leaders default to **all hitter positions** (C, 1B, 2B, … — not the legacy **H** chip). **H** / **P** shortcuts still select full hitter or pitcher groups; do **not** mix hitters and pitchers. **Two-way** players (e.g. Ohtani): separate **hitting / pitching** season rows, profile game-log toggle, and role-specific stat columns. **Mid-season trades** = one row per team after re-ingest. **Career Z** omitted for **2020** (shortened season). BRef + FanGraphs ingest; BRef from **2008**. Season counting stats use MLB Stats API **regular season** totals (`gameType=R`; BRef `G`/`HR`/etc. can include postseason).
- **NBA / MLB / NHL:** Player Profile season detail is **per-game** (game log chart/table, game-level boom/bust). Draft ECR vs finish rank on leaders when `ingest_sport_rankings.py` has been run (no weekly FP consensus ingest in the UI).
- **NBA:** Season totals from `LeagueDashPlayerStats`; leaders default to **all positions** (PG–C). Draft/weekly ECR default to **`position=ALL`** with positional reorder in code (use `--positional-boards` if needed). Positions from team rosters + `PlayerIndex` fallback (cache under `data/cache/nba/`). Use `scripts/ingest_nba.py --index-only` for faster lookup, or `--refresh-positions` to refetch. Game logs: bulk league download by default; avoid `--per-player-only` unless bulk fails
- **MLB / NHL game logs:** One API call per player (large seasons). **Regular season only** (MLB `gameType=R`, NBA `Regular Season`, NHL `gameTypeId=2`). MLB: **hitting** + **pitching** rows; NHL: **skater** + **goalie** rows (`log_type`). Disk cache under `data/cache/gamelogs/`; `--refresh-cache` after schema changes. NHL: **3 workers**, **0.65s** delay; on `429` backs off. If rate-limited: `--workers 2 --delay 1.0`
- **NHL:** Season Leaders default to **all skater positions** (C, LW, RW, D, F — not the legacy **S** chip). **S** / **G** shortcuts still work; do **not** mix skaters and goalies. Draft ECR uses positional FP boards when available (`/players` fallback). **Mid-season trades** = one row per team after re-ingest

### App

- **Multi-sport home:** `st.navigation` + nested pages (Streamlit **1.36+**)
- **Repair database** (sidebar, all sports): NFL games played, player index, display names, weekly **opponent**, D/ST **points/yards allowed**, MLB **accented player names**, **H → DH** hitter positions, and **regular-season MLB stat overlay** (fixes BRef totals that include postseason), NBA **positions from team rosters**
- **Season labels (sidebar):** **NFL/MLB** use **calendar year** (e.g. `2024` = that MLB/NFL season). **NBA/NHL** use **season end year** (e.g. `2025` = 2024–25). Caption shown under the season control on every page

## Data sources

All stats land in local **DuckDB** (`data/fantasy_tracker.duckdb`). Nothing is bundled with the repo — every ingest hits live APIs or scraped pages. Respect each provider’s terms when redistributing derived data (see [License](#license)).

| What | Provider / package | Endpoint or dataset | Used for | API key? |
|------|-------------------|---------------------|----------|----------|
| **NFL weekly + season offense** | [nflverse](https://github.com/nflverse) via [`nflreadpy`](https://nflreadpy.nflverse.com/) | `load_player_stats` | QB/RB/WR/TE/K weekly rows, season aggregates | No |
| **NFL team defense** | nflverse | `load_team_stats` | Sacks, turnovers, TDs; opponent pass/rush yards for D/ST | No |
| **NFL schedules** | nflverse | `load_schedules` | Weekly **opponent**; D/ST **points allowed** (final scores) | No |
| **NFL player index** | nflverse | `load_players` | Search / display names (maintenance backfill) | No |
| **NFL draft + weekly ECR** | nflverse | `load_ff_rankings`, `load_ff_playerids` | Expert consensus ranks vs finish; FP→GSIS ID map | No |
| **MLB season batting/pitching** | [pybaseball](https://github.com/jldbc/pybaseball) → [Baseball Reference](https://www.baseball-reference.com/) | `batting_stats_bref`, `pitching_stats_bref` | Season leaders, profiles, compare (bulk from **2008**) | No |
| **MLB regular-season stats** | [MLB Stats API](https://statsapi.mlb.com/) | `stats=season`, `gameType=R` | Corrects BRef season totals (often include postseason); ingest + **Repair database** | No |
| **MLB season (fallback)** | pybaseball → [FanGraphs](https://www.fangraphs.com/) | `batting_stats`, `pitching_stats` | Used when BRef fails; bulk often **403** | No |
| **MLB field positions** | BRef HTML + FanGraphs | BRef standard batting page; FG position table | CF, 1B, SP, RP, etc. (`position_lookup.py`) | No |
| **MLB player IDs / positions** | [MLB Stats API](https://statsapi.mlb.com/) | `GET /api/v1/sports/1/players?season=` | Primary position by MLBAM id during ingest | No |
| **MLB game logs** | MLB Stats API | `GET /api/v1/people/{id}/stats` (`gameLog`, hitting + pitching) | Profile per-game tables; **one request per player** | No |
| **NBA season totals** | [nba_api](https://github.com/swar/nba_api) → [stats.nba.com](https://stats.nba.com/) | `LeagueDashPlayerStats` | Season leaders, profiles | No |
| **NBA positions** | nba_api | `CommonTeamRoster` (default), `PlayerIndex` (fallback) | PG–C buckets; roster cache under `data/cache/nba/` | No |
| **NBA game logs** | nba_api | `PlayerGameLogs` (bulk, monthly chunks); `PlayerGameLog` (fallback) | Profile per-game tables | No |
| **NHL season stats** | [nhl-api-py](https://github.com/coreyjs/nhl-api-py) (`nhlpy`) → NHL API | Skater + goalie season endpoints (paginated) | Season leaders, profiles (from **2005**) | No |
| **NHL game logs** | NHL API | `api-web.nhle.com/v1/player/{id}/game-log/{season}/2` | Skater + goalie per-game rows; **one request per player** | No |
| **MLB/NBA/NHL draft ECR** | [FantasyPros Public API v2](https://api.fantasypros.com/public/v2/docs) | `consensus-rankings?position=ALL&week=0` (optional `--positional-boards`) | Draft rank vs **positional** finish (name-matched) | **`FANTASYPROS_API_KEY`** |
| **MLB/NBA/NHL weekly ECR** | FantasyPros Public API (optional) | `consensus-rankings?position=ALL&week=N` (~26 calls/season) | Not used in app UI; draft ECR only is the supported path | **`FANTASYPROS_API_KEY`** |
| **MLB/NBA/NHL projections** | FantasyPros Public API | `/{sport}/{season}/projections?position=ALL` (one call) | Optional projection tables | **`FANTASYPROS_API_KEY`** |
| **MLB/NBA FP positions** | FantasyPros Public API | `/{SPORT}/players` | Position overlay on ingested stats | **`FANTASYPROS_API_KEY`** |

**Not external data:** ESPN-style fantasy points are computed locally from [`src/scoring/`](src/scoring/) presets (NFL offense/kicker/D/ST YAML + optional custom NFL presets in DuckDB). Peer Z volume gates live in [`src/analytics/thresholds.yaml`](src/analytics/thresholds.yaml).

**Local disk caches (gitignored):** `data/cache/gamelogs/` (MLB/NHL/NBA game-log pickles), `data/cache/fantasypros/` (FP `/players` JSON), `data/cache/nba/` (roster position maps). Caches speed **retries and resume**; they do not replace the upstream sources above.

NFL weekly rows include **opponent** (`opponent_team`). D/ST **points allowed** are not in nflverse team box scores — we join **schedules** (`home_score` / `away_score`). **Yards allowed** = opponent **passing + rushing** yards in the same game.

After schema or ingest-logic changes, **re-ingest** affected seasons and/or run sidebar **Repair database**.

**Important:** MLB and NHL season tables now store **one row per player × season × position × team**. Re-ingest those sports after upgrading so trade splits and team filters work correctly.

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

# Minimal NFL smoke test (required before NFL pages show data)
.\.venv\Scripts\python.exe scripts\ingest_season.py --season 2023

# Run app → http://localhost:8501
.\.venv\Scripts\python.exe -m streamlit run app/Home.py
```

Database: `data/fantasy_tracker.duckdb` (gitignored).

For a **full multi-sport load** (season stats, game logs, rankings, FantasyPros), see **[Loading all data](#loading-all-data)** below. For the complete upstream source list, see **[Data sources](#data-sources)**.

**Sidebar:** scoring preset (NFL offense: built-ins or saved **★ custom** presets), **Custom scoring presets** expander, **season view** (single / range / pick) with a **season-year hint** (calendar vs end year), min games, optional peer Z (era). **Repair database** (every sport) runs maintenance backfills (see Features).

**Custom scoring (v1):** NFL offense only (QB/RB/WR/TE). Points are computed at query time from weekly/season stat columns. Built-in presets still use precomputed `fantasy_points_*` from ingest. See [docs/CUSTOM_SCORING.md](docs/CUSTOM_SCORING.md).

## Loading all data

This is the recommended order to populate `data/fantasy_tracker.duckdb`. Each phase builds on the previous one. Bulk ingests are **safe to stop and resume** — re-run the same command; skipped seasons are logged and can be retried individually.

**Most ingests are slow by design.** We pull from public APIs and scraped pages with polite delays and retries. A **minimal** load (one recent NFL season) takes minutes; a **full multi-sport history with game logs** can run **overnight to several days** on a home connection. Plan accordingly — run long jobs in a persistent terminal, start with the sports/years you care about, and use disk caches so interrupted runs resume without refetching everything.

### Expected duration (rough order of magnitude)

Times vary with network, rate limits, and machine speed. Treat these as planning guides, not guarantees.

| Job | Typical scope | Rough time | Why it’s slow |
|-----|---------------|------------|---------------|
| Single NFL season | `--season 2023` | **1–5 min** | One nflverse download + local aggregation |
| NFL bulk season stats | 1999–2025 (~27 seasons) | **30–90 min** | One season at a time; weekly + team + schedule per year |
| Single MLB season (BRef) | `--season 2024 --source bref` | **2–10 min** | Batting + pitching scrape with retries |
| MLB bulk season stats | 2008–2025 (~18 seasons) | **1–3 hours** | BRef rate limits; **3 s pause** between seasons by default |
| NBA bulk season stats | 2000–2025 (~26 seasons) | **1–3 hours** | One stats call per season + **~30 team roster** calls each for positions |
| NHL bulk season stats | 2005–2025 (~21 seasons) | **30–90 min** | Paginated skater + goalie API; **1 s pause** between seasons |
| NFL rankings | `ingest_rankings.py` | **5–20 min** | nflverse ECR history download |
| FantasyPros sport rankings | one sport × one recent season | **minutes–hours** | **~100 API calls/day** per key; default **`position=ALL`** (1 call/draft, 1/week); split `--weeks` across days |
| **NBA game logs** | one season | **5–20 min** | Bulk `PlayerGameLogs` (~9 monthly chunks + retries) |
| **MLB game logs** | one season | **30 min – 2 hours** | **One MLB Stats API call per player** (~600–800+ players); 6 workers |
| **NHL game logs** | one season | **1–4 hours** | **One NHL API call per player**; default **0.65 s** spacing + 429 backoff |
| **MLB game logs bulk** | 2008–2025 | **1–3+ days** | Players × seasons; cache makes **resume** cheap |
| **NHL game logs bulk** | 2005–2025 | **2–5+ days** | Same pattern; use `--workers 2 --delay 1.0` if rate-limited |

**Practical tips:**

- **Phase 1 first, game logs last** — leaders and compare work without Phase 2; game logs are the long pole.
- **Ingest recent years first** if you want the app usable quickly, then backfill history.
- **Do not run multiple bulk game-log ingests** against the same sport in parallel — you will hit rate limits faster.
- **Caches are your friend** — `data/cache/gamelogs/` and `data/cache/fantasypros/` let you stop and continue; use `--refresh-cache` only after parser/schema changes.
- **MLB BRef bulk** may skip years — check `data/ingest_failures_mlb.log` and retry with `--season YEAR --source bref`.

### What you need

| Requirement | Required for |
|-------------|----------------|
| **Python 3.12+ venv** + `pip install -r requirements.txt` | Everything |
| **Internet** during ingest | All external APIs (nflverse, BRef, nba_api, NHL, FantasyPros) |
| **`FANTASYPROS_API_KEY`** | MLB/NBA/NHL **draft ECR**, **projections**, and **FP position overlay** on NBA/MLB — **not** needed for core season stats or NFL rankings |
| **Time** | Full history is **hours to days** (season stats) or **days** (MLB/NHL game logs) — see [Expected duration](#expected-duration-rough-order-of-magnitude) |

Nothing in this repo ships with live API keys. Copy [`.env.example`](.env.example) → `.env` (gitignored) or set the variable in your shell:

```powershell
# Project root .env (preferred — auto-loaded by ingest scripts)
copy .env.example .env
# Edit .env and set: FANTASYPROS_API_KEY=your_key_here

# Or for one PowerShell session:
$env:FANTASYPROS_API_KEY = "your_key_here"
```

Test FantasyPros access before running sport rankings ingest:

```powershell
.\.venv\Scripts\python.exe scripts\fantasypros_probe.py
```

Public API docs: [https://api.fantasypros.com/public/v2/docs](https://api.fantasypros.com/public/v2/docs)

**FantasyPros Public API — daily call budget (important):**

The Public API tier is roughly **100 HTTP calls per day per API key**. Hitting the cap returns **HTTP 429**; spacing requests helps pacing but does **not** raise the daily limit.

| Operation | Default calls | Notes |
|-----------|---------------|--------|
| Draft ECR (one season) | **1** | `consensus-rankings?position=ALL&week=0` |
| Weekly ECR (optional; not in UI) | **~26** | **1 GET per week** — only if you experiment outside the app |
| Draft + projections (one run) | **2** | One consensus + one projections (`position=ALL`) |
| `refresh_fp_positions.py` | **0–1** | `/players` cached ~7 days under `data/cache/fantasypros/` |
| `fantasypros_probe.py` | **~10+** | Counts against the same quota — run sparingly |
| `--positional-boards` | **3–5× per week/draft** | Emergency only; default ingest always uses **`position=ALL`** and reorders positions in code |

**Recommended for MLB/NBA/NHL:** draft ECR only (1 call/season). Skip `--weekly` unless you are experimenting — it does not power the app UI.

Other limitations:

- URL params like `season >= 2012` are valid, but **consensus rankings and projections often return the current player pool** for old years — ingest refuses to load when names do not match that season (`fp_season_mismatch`).
- On **429**, wait for the daily window to reset (or use cache). Defaults: **`--delay 8 --fp-min-interval 8`** for `--weekly`; increase to **10** if you still see 429 while under the daily cap.
- Beat-draft-rank and weekly surprise use **positional** finish ranks; that comes from **`assign_positional_ecr_ranks`** after the single `ALL` board — not from separate FP position endpoints.

### Phase 1 — Season stats (required for Leaders / Profile / Compare)

These scripts create the core tables. **Run these before game logs or rankings** (game logs read player lists from season stats). Bulk runs process **one season at a time** with pauses where upstream sources rate-limit.

| Sport | Script | Typical bulk range | Notes | Slowness |
|-------|--------|-------------------|--------|----------|
| **NFL** | `scripts/ingest_season.py` | 1999–2025 | REG weeks only; D/ST + kicker scoring from nflverse | ~1–3 min/season |
| **MLB** | `scripts/ingest_mlb.py` | 2008–2025 | Use `--source bref` for bulk; BRef rate limits → `--delay`, `--failure-log`. **Games** overlaid from MLB Stats API (regular season). | ~5–15 min/season; **3 s** between bulk years (BRef) |
| **NBA** | `scripts/ingest_nba.py` | 2000–2025 | Positions from team rosters by default (disk cache under `data/cache/nba/`) | ~3–8 min/season (roster fetches dominate) |
| **NHL** | `scripts/ingest_nhl.py` | 2005–2025 | Season end year (e.g. 2025 = 2024–25) | ~2–5 min/season |

**Full season-stats bootstrap (PowerShell):**

```powershell
# NFL — full history (long; one season at a time internally)
.\.venv\Scripts\python.exe scripts\ingest_season.py --bulk --from-year 1999 --to-year 2025

# MLB — BRef from 2008 (FanGraphs often 403; bulk uses bref)
.\.venv\Scripts\python.exe scripts\ingest_mlb.py --bulk --from-year 2008 --to-year 2025 --source bref

# NBA
.\.venv\Scripts\python.exe scripts\ingest_nba.py --bulk --from-year 2000 --to-year 2025

# NHL
.\.venv\Scripts\python.exe scripts\ingest_nhl.py --bulk --from-year 2005 --to-year 2025
```

Or use the unified wrapper:

```powershell
.\.venv\Scripts\python.exe scripts\ingest.py --sport nfl --bulk --from-year 1999 --to-year 2025
.\.venv\Scripts\python.exe scripts\ingest.py --sport mlb --bulk --from-year 2008 --to-year 2025 --source bref
.\.venv\Scripts\python.exe scripts\ingest.py --sport nba --bulk --from-year 2000 --to-year 2025
.\.venv\Scripts\python.exe scripts\ingest.py --sport nhl --bulk --from-year 2005 --to-year 2025
```

**After Phase 1:** open the app — sport hubs should show leaders and profiles for ingested seasons. NFL weekly opponent / D/ST backfills may need **Repair database** (sidebar) or Phase 5 maintenance.

**Resume a failed year:**

```powershell
.\.venv\Scripts\python.exe scripts\ingest_mlb.py --season 2019 --source bref
.\.venv\Scripts\python.exe scripts\ingest_season.py --season 2012
```

### Phase 2 — Game logs (optional; Player Profile per-game tables)

Game logs are **separate, much slower ingests** — often the longest step in a full load. They power profile **game log tables**, strong/weak game highlighting, and per-game charts — not season leaders. MLB and NHL fetch **one HTTP request per player per season**; expect **hours per season** and **days** for full history (see duration table above).

| Sport | Script | Bulk helper | Default range | Notes | Slowness |
|-------|--------|-------------|---------------|--------|----------|
| **MLB** | `ingest_mlb_gamelogs.py` | `ingest_mlb_nhl_gamelogs.py --sport mlb` | 2008+ | Regular season (`gameType=R`); hitting + pitching rows | **Slowest** — MLB Stats API per player; 6 workers, disk cache |
| **NHL** | `ingest_nhl_gamelogs.py` | `ingest_mlb_nhl_gamelogs.py --sport nhl` | 2005+ | Skater + **goalie** rows; throttle with `--workers 2 --delay 1.0` if 429 | Very slow — **0.65 s** default spacing; 429 backoff |
| **NBA** | `ingest_nba_gamelogs.py` | `ingest_sport_gamelogs.py --sport nba` | after NBA stats | Bulk league API by default | **Fastest** game logs — ~9 bulk calls/season |

**Requires Phase 1** for that sport and season (player list comes from `*_player_season_stats`).

```powershell
# MLB + NHL bulk game logs (MLB from 2008, NHL from 2005)
.\.venv\Scripts\python.exe scripts\ingest_mlb_nhl_gamelogs.py

# NHL only, rate-limit friendly
.\.venv\Scripts\python.exe scripts\ingest_mlb_nhl_gamelogs.py --sport nhl --workers 2 --delay 1.0

# Single season / sport
.\.venv\Scripts\python.exe scripts\ingest_sport_gamelogs.py --sport mlb --season 2024
.\.venv\Scripts\python.exe scripts\ingest_nba_gamelogs.py --season 2024
```

Disk cache: `data/cache/gamelogs/{sport}/{season}/` — re-run the same command to resume. Use `--refresh-cache` after schema or parser changes.

### Phase 3 — FantasyPros (MLB / NBA / NHL) — **`FANTASYPROS_API_KEY` required**

Used for **draft ECR**, optional **projections**, and (via a separate script) **position overlays**. Does **not** replace Phase 1 stats — FP has no shared IDs with BRef/nba_api/nhlpy; names are fuzzy-matched at ingest.

**Always `position=ALL` for consensus and projections** (one HTTP GET per draft board, per week, or per projections fetch). Positional ECR for analytics is derived in Python (`assign_positional_ecr_ranks`), not by calling PG/SG/SP/etc. endpoints — those are only available via **`--positional-boards`** when the `ALL` board fails your probe.

Plan around **~100 Public API calls/day**. Draft + projections for three sports is a few calls; a full **`--weekly`** backfill (~26 calls/season each) burns most of a day and is **not wired into the app** anymore. Ingest scripts still support `--weekly` for experiments; cache under `data/cache/fantasypros/` if you use it.

| Script | Purpose | API key? |
|--------|---------|----------|
| `scripts/ingest_sport_rankings.py` | Draft ECR → `ecr_draft`; optional weekly → `ecr_weekly` (not in UI); projections → `fp_projections` | **Yes** |
| `scripts/refresh_fp_positions.py` | Overlay FP positions on NBA/MLB season stats | **Yes** |
| `scripts/rankings_coverage.py` | Report ECR match rate vs ingested stats | No (reads DB only) |
| `scripts/diag_fp_nba_match.py` | Debug name overlap for a season | **Yes** |

```powershell
# Draft ECR (default: one position=ALL call + in-code positional reorder)
.\.venv\Scripts\python.exe scripts\ingest_sport_rankings.py --sport nba --season 2025 --delay 1.5
.\.venv\Scripts\python.exe scripts\ingest_sport_rankings.py --sport mlb --season 2025 --delay 1.5
.\.venv\Scripts\python.exe scripts\ingest_sport_rankings.py --sport nhl --season 2025 --delay 1.5

# Projections only (one position=ALL call)
.\.venv\Scripts\python.exe scripts\ingest_sport_rankings.py --sport mlb --season 2025 --projections-only

# Fix positions on already-ingested NBA/MLB rows
.\.venv\Scripts\python.exe scripts\refresh_fp_positions.py --sport nba
.\.venv\Scripts\python.exe scripts\refresh_fp_positions.py --sport mlb --season 2024
```

Check coverage after ingest:

```powershell
.\.venv\Scripts\python.exe scripts\rankings_coverage.py --sport nba --season 2025
```

### Phase 4 — NFL draft & weekly ECR (no FantasyPros API key)

NFL expert rankings come from **nflverse** (bundled FantasyPros ECR history), not the Public API:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_rankings.py
```

Powers NFL **Winners & losers**, draft ECR vs finish rank, and weekly ECR on profiles when weekly data exists.

### Phase 5 — Maintenance & validation

Run after bulk ingests or schema upgrades:

```powershell
# Sidebar "Repair database" does the same backfills in the UI. CLI equivalent:
.\.venv\Scripts\python.exe -c "from src.db.connection import get_connection, init_schema; from src.db.maintenance import backfill_dst_points_allowed, backfill_mlb_player_names, backfill_mlb_regular_season_games, backfill_weekly_opponents, recompute_games_played, rebuild_players_table, refresh_player_display_names; init_schema(); c=get_connection(); recompute_games_played(c); rebuild_players_table(c); refresh_player_display_names(c); backfill_weekly_opponents(c); backfill_dst_points_allowed(c); backfill_mlb_player_names(c); backfill_mlb_regular_season_games(c); c.close()"

# Peer-Z volume gate sanity check
.\.venv\Scripts\python.exe scripts\volume_report.py --season 2023 --sport nfl
.\.venv\Scripts\python.exe scripts\volume_report.py --season 2024 --sport mlb
```

**Re-ingest** MLB/NHL season stats after upgrading if you need correct **trade splits** (one row per player × season × position × team).

### Suggested “everything” checklist

Use this as a runbook; adjust `--to-year` to the current season.

1. `check_env.py`
2. Copy `.env` + set `FANTASYPROS_API_KEY` → `fantasypros_probe.py`
3. Phase 1 bulk for NFL, MLB, NBA, NHL
4. Sidebar **Repair database** once
5. Phase 2 game logs (**optional; plan overnight** — MLB/NHL full history is multi-day)
6. Phase 4 NFL `ingest_rankings.py`
7. Phase 3 FP rankings for recent MLB/NBA/NHL seasons you analyze
8. `refresh_fp_positions.py` for NBA/MLB if FP positions beat roster/BRef defaults
9. `rankings_coverage.py` / `volume_report.py` to validate

### What works without FantasyPros

| Feature | Without FP key |
|---------|----------------|
| Season leaders, profiles, compare (all sports) | Yes |
| NFL weekly stats, D/ST, custom scoring | Yes |
| MLB/NBA/NHL season stats & game logs | Yes |
| NFL draft/weekly ECR (nflverse) | Yes |
| MLB/NBA/NHL draft ECR & projections | **No** |
| FP-based position overlay (NBA/MLB) | **No** (roster/BRef positions still used from Phase 1) |

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
| MLB hitters only vs pitchers only | **MLB Season Leaders** — **H** or **P** / **SP** / **RP** (not both) |
| NHL skaters only vs goalies only | **NHL Season Leaders** — **S** or **G** (not both) |
| Filter leaders by team (MLB/NHL) | **Team** dropdown — traded players appear once per stint |
| Open a leader in full profile | Click **Player** name on Season Leaders (NFL, MLB, NBA, NHL) |
| Share a profile link | **Player Profile** — URL `?entity=` / `?season=` |
| Tune peer Z volume gates | `scripts/volume_report.py --season 2023` (NFL) or `--sport mlb` / `nba` / `nhl` |

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
| `scripts/ingest_mlb.py` | MLB (`--season`, `--bulk`, `--seasons`; `--source auto\|bref\|fangraphs`; `--delay`; `--retries`; `--failure-log`; `--fail-fast`) |
| `scripts/ingest_nba.py` | NBA (`--bulk --from-year 2000` typical; `--refresh-positions`, `--index-only`) |
| `scripts/ingest_nhl.py` | NHL (`--bulk --from-year 2005` typical) |
| `scripts/ingest_rankings.py` | FantasyPros ECR (NFL) from nflverse |
| `scripts/ingest_sport_rankings.py` | FantasyPros draft ECR + projections (MLB/NBA/NHL; needs `FANTASYPROS_API_KEY`) |
| `scripts/refresh_fp_positions.py` | Overlay FantasyPros positions on ingested NBA/MLB stats (`FANTASYPROS_API_KEY`) |
| `scripts/rankings_coverage.py` | Draft ECR vs stats ingest coverage |
| `scripts/volume_report.py` | Peer-Z volume gate check (`--season YEAR`, `--sport` nfl / mlb / nba / nhl) |
| `scripts/ingest_sport_gamelogs.py` | Unified game logs (`--sport mlb\|nba\|nhl`, `--season`, MLB/NHL: `--workers`, `--no-cache`, `--refresh-cache`) |
| `scripts/ingest_mlb_nhl_gamelogs.py` | Bulk MLB (from 2008) + NHL (from 2005) game logs; needs season stats ingested first |
| `scripts/ingest_nba_gamelogs.py` | NBA per-game rows (bulk by default; `--per-player-only` if needed) |
| `scripts/ingest_mlb_gamelogs.py` | MLB per-game rows (`--workers` default 6, disk cache on) |
| `scripts/ingest_nhl_gamelogs.py` | NHL skater + goalie per-game rows (`--workers` default 3, `--delay 0.65`) |
| `scripts/fantasypros_probe.py` | Test `FANTASYPROS_API_KEY` / Public API connectivity |
| `scripts/diag_fp_nba_match.py` | Debug FantasyPros name overlap for a season |
| `scripts/rebuild_players.py` | Rebuild NFL player search index |
| `scripts/check_env.py` | Python arch, packages, DB presence |

Resume a failed bulk ingest from a year (see also [Loading all data](#loading-all-data)):

```powershell
.\.venv\Scripts\python.exe scripts\ingest_season.py --bulk --from-year 2001 --to-year 2025
.\.venv\Scripts\python.exe scripts\ingest_mlb.py --season 2024 --source bref
```

**Maintenance from CLI** (same as sidebar Repair database):

```powershell
.\.venv\Scripts\python.exe -c "from src.db.connection import get_connection, init_schema; from src.db.maintenance import backfill_dst_points_allowed, backfill_mlb_player_names, backfill_mlb_regular_season_games, backfill_weekly_opponents, recompute_games_played, rebuild_players_table, refresh_player_display_names; init_schema(); c=get_connection(); recompute_games_played(c); rebuild_players_table(c); refresh_player_display_names(c); backfill_weekly_opponents(c); backfill_dst_points_allowed(c); backfill_mlb_player_names(c); backfill_mlb_regular_season_games(c); c.close()"
```

## Configuration

| File | What it controls |
|------|------------------|
| [`src/scoring/presets.yaml`](src/scoring/presets.yaml) | Built-in NFL offense (Standard / Half-PPR / Full PPR) |
| `scoring_presets` table (DuckDB) | Saved custom NFL offense presets |
| [`src/scoring/kicker_presets.yaml`](src/scoring/kicker_presets.yaml) | ESPN kicker scoring |
| [`src/scoring/dst_presets.yaml`](src/scoring/dst_presets.yaml) | ESPN D/ST (events + PA + yards tiers) |
| [`config/settings.yaml`](config/settings.yaml) | Default min games for leaderboards (8; NFL-oriented) |
| [`src/analytics/thresholds.yaml`](src/analytics/thresholds.yaml) | Volume gates for peer Z (NFL positions + `volume_gates_by_sport` for MLB/NBA/NHL) |
| [`.streamlit/config.toml`](.streamlit/config.toml) | Theme; `fileWatcherType = none` |

Re-ingest after schema, position-filter, or D/ST/MLB ingest logic changes.

## Project layout

```
app/                    Streamlit: Home.py + navigation.py + pages/{nfl,mlb,nba,nhl}/
                        sport_leaders_page.py (MLB/NBA/NHL); nfl_leaders_page.py (NFL)
src/sports/             Per-sport plugins (registry, positions, queries, scoring)
src/analytics/          Z-scores, consistency, surprise vs ECR; sport_surprise (MLB/NBA/NHL)
src/team_dst_columns.py NFL D/ST mapping, PA/yards from schedules + team stats
src/text_encoding.py    Unicode repair for scraped names (MLB, etc.)
src/season_selection.py Sidebar season window helpers
src/scoring/            Presets, custom store, query-time FP SQL
src/db/                 DuckDB schema, queries, maintenance backfills
scripts/                Ingest and utilities
docs/                   Roadmaps and design notes
data/                   Local DuckDB (gitignored)
```

Docs: [docs/ENHANCEMENT_ROADMAP.md](docs/ENHANCEMENT_ROADMAP.md), [docs/CUSTOM_SCORING.md](docs/CUSTOM_SCORING.md), [docs/MULTISPORT_ROADMAP.md](docs/MULTISPORT_ROADMAP.md), [docs/NEXT_SESSION_PLAN.md](docs/NEXT_SESSION_PLAN.md) (volume gates by sport, PA for MLB hitters, ingest performance).

## Troubleshooting

Run `.\.venv\Scripts\python.exe scripts\check_env.py` first.

| Issue | What to do |
|-------|------------|
| `ModuleNotFoundError: nflreadpy` | Use `.\.venv\Scripts\python.exe`, not bare `python`; run `pip install -r requirements.txt` |
| `python` not found / Store opens | Install 64-bit Python; use `py -3.12`; disable App execution aliases |
| pandas build / Meson errors | **32-bit Python** — recreate venv (64-bit) and reinstall requirements |
| `Activate.ps1` blocked | Skip activation; use `.\.venv\Scripts\python.exe` for all commands |
| Empty Season Leaders | Lower min games; re-ingest; **Repair database**; check position filter (clearing all tags shows “select at least one position”) |
| Absurd **draft ECR** / rank delta (e.g. 147) on MLB/NBA | Re-run `ingest_sport_rankings.py` (default `position=ALL` + in-code positional reorder); only use `--positional-boards` if `ALL` fails probe |
| FantasyPros **429** on weekly ingest | Often **daily cap (~100 calls)** — split `--weeks` across days; re-run same command (cache = 0 calls); avoid `fantasypros_probe.py` before big ingests |
| D/ST **points/yards allowed** all zero | **Repair database** or re-ingest NFL; PA needs schedules, yards need team stats |
| MLB names like `Jos\xc3\xa9` | **Repair database** or re-ingest MLB (`src/text_encoding.py` fixes on read + backfill) |
| MLB positions all **H** / **P** in **stored stats** | Re-ingest MLB; new ingests store **CF, 1B, SP, RP**, etc. Leaders UI defaults to explicit field positions; **H**/**P** remain shortcuts |
| **Few players labeled DH** on MLB leaders | Expected: position is **primary field** from BRef `Pos` (first token in `1B-DH`) or MLB Stats API, not game-level DH. True DHs with no field pos fall back to **DH**; most DH-eligible stars stay **1B/OF/LF**. Filter **H** or multiple positions — not **DH** only. `scripts/mlb_position_report.py` shows counts |
| Missing **Opponent** (NFL weekly) | **Repair database** or re-ingest that season |
| Player not in search | Type 2+ letters; **Repair database** or `scripts/rebuild_players.py` |
| MLB BRef bulk skips seasons | Retry with `--season YEAR --source bref`; use `--fail-fast` to stop on first error |
| MLB **HR/games** look too high (postseason included) | BRef totals can include playoffs; re-ingest MLB or **Repair database** for MLB Stats API regular-season overlay |
| MLB profile game log shows batting cols for a pitcher | Re-ingest game logs with `--refresh-cache`; pitching view uses wins / K / IP columns |
| NBA everyone shows **SF** | **Repair database** or re-ingest; positions come from **team rosters** (PlayerIndex join uses normalized player IDs) |
| NHL partial seasons | nhlpy caps page size; re-ingest affected years with current `ingest_nhl.py` |
| NHL positions all **S** / **G** in **stored stats** | Re-ingest NHL; new ingests store **C, LW, RW, D** and **G**. Leaders UI defaults to skater positions; **S**/**G** remain shortcuts |
| MLB/NHL leader shows wrong team or one row per player | Re-ingest that sport — storage is per **team stint**; combined `2TM`/`TOT` rows are dropped when splits exist |
| Mixed hitter + pitcher on MLB leaders | Pick hitters **or** pitchers only; UI coerces away from mixing (like NFL K/DST) |
| Mixed skater + goalie on NHL leaders | Pick skaters **or** goalies only; same coercion rules |
| Cleared position filter refills everything | Fixed: removing all tags leaves filter empty (narrow with **×** on chips; MLB/NHL/NFL/NBA) |
| NHL game logs slow / HTTP 429 | Use `--workers 2 --delay 1.0`; cache under `data/cache/gamelogs/nhl/` lets you resume |
| FantasyPros `429` / empty MLB rankings | Daily cap or cooldown — wait and resume; cached consensus under `data/cache/fantasypros/` |
| `fp_season_mismatch` on old NBA/MLB seasons | FP often returns current-era players for old URLs — use recent seasons only |
| `FANTASYPROS_API_KEY` not set | Copy `.env.example` → `.env` or `$env:FANTASYPROS_API_KEY`; run `fantasypros_probe.py` |
| `ImportError` from `peer_z` on MLB/NBA/NHL leaders | Use `peer_z_sport` module (fixed in app); upgrade and restart Streamlit |
| Profile shows raw column names or wrong stats | Restart app; MLB/NHL profiles use role-specific stat columns (hitting vs pitching, etc.) |
| Streamlit nested pages / duplicate URLs | Requires Streamlit **≥1.36**; entrypoint is `app/Home.py` |
| Custom preset not on pages | Save preset, select **★** in **Scoring** |

Expected NFL ingest: `Dropped N weekly rows` (non-skill positions). Bulk ingest is **one season at a time** — safe to resume mid-range.

## License

MIT — see [LICENSE](LICENSE). NFL data via nflverse is CC-BY 4.0. Respect terms for [Baseball Reference](https://www.baseball-reference.com/about/terms-of-use.shtml), [FanGraphs](https://www.fangraphs.com/about/terms-of-service/), [stats.nba.com](https://www.nba.com/termsofuse), [NHL API](https://www.nhl.com/info/terms-of-service), [MLB Stats API](https://www.mlb.com/official-information/terms-of-use), and [FantasyPros](https://www.fantasypros.com/about/terms/) when redistributing data.

## Contributing

PRs welcome. Before submitting:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
```
