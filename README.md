# Fantasy Tracker

Open-source NFL fantasy analytics for **completed regular seasons** — season leaders, player careers, head-to-head compare, and Z-scores vs peers and career baselines.

Inspired by [NFL Perry](https://www.nflperry.com/) for data use cases, focused on historical analysis (not gameplay).

## Features

- **Scoring:** Standard, Half-PPR, Full PPR for offense; **ESPN default** for kickers and team D/ST
- **Season window (sidebar):** **Single season**, **season range**, or **pick seasons** — drives Leaders, Profile, and Compare
- **Season Leaders:** QB/RB/WR/TE/K plus **DST**; sortable FP/G; **window leaders** when multiple years are selected; clickable names → Profile
- **Player Profile:** **Career & window** (season table, peak/prime, career chart) and **season detail** (peer Z, consistency, weekly opponent, boom/bust weeks)
- **Compare:** **All-time**, **single season** (same year for both), or **selected seasons** (sidebar window; cross-era OK)
- **Variance:** Peer Z (season), optional peer Z (era), career Z; volume gates in [`src/analytics/thresholds.yaml`](src/analytics/thresholds.yaml)

## Data

- [nflverse](https://github.com/nflverse) via [`nflreadpy`](https://nflreadpy.nflverse.com/)
- **1999+** regular seasons only; ingest ad-hoc when a season completes
- Players: **QB, RB, WR, TE, K**; team **D/ST** from nflverse team stats (see [`src/positions.py`](src/positions.py))
- Weekly rows include **opponent** team (from nflverse `opponent_team`)

After schema changes (kickers, D/ST, opponent, etc.), **re-ingest** affected seasons or use sidebar **Repair database**:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_season.py --season 2023
```

## Quick start

**Python 3.12+**, **64-bit** recommended. Use the venv interpreter directly (no need to activate on Windows):

```powershell
cd fantasy-tracker
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps

# Ingest (required before the app shows data)
.\.venv\Scripts\python.exe scripts\ingest_season.py --season 2023
# Or full history:
.\.venv\Scripts\python.exe scripts\ingest_season.py --bulk --from-year 1999 --to-year 2025

# Run app → open http://localhost:8501
.\.venv\Scripts\python.exe -m streamlit run app/Home.py
```

Database: `data/fantasy_tracker.duckdb` (gitignored).

**Sidebar:** scoring preset, **season view** (single / range / pick), min games, optional peer Z (era). **Repair database** rebuilds player index, fixes games played, refreshes display names, and backfills weekly **opponent** columns.

## What you can do

| Question | Where |
|----------|--------|
| Who were the top half-PPR RBs in 2022 with at least 8 games? | **Season Leaders** — sidebar single season 2022, position RB, Half-PPR |
| Who dominated 2018–2022 on total points and per game? | **Season Leaders** — sidebar **season range** 2018–2022; window totals and FP/G |
| How does a player’s 2021 compare to their own career? | **Player Profile** — **Career Z** on the season row in **Career & window** |
| How elite was a season vs peers that year? | **Player Profile** → **Season detail** — **Peer Z (season)**; sidebar **peer Z (era)** for historical baseline on career table |
| Was he consistent or boom/bust? | **Player Profile** → **Season detail** — consistency panel and weekly table |
| Compare Kelce vs Andrews in 2023 only | **Compare** — **Single season**; sidebar 2023; both must have played that year |
| Compare Manning vs Mahomes careers (different eras) | **Compare** — **All-time** |
| Compare two players over 2018–2022 only | **Compare** — sidebar range 2018–2022, mode **Selected seasons** |
| Top defenses or kickers | **Season Leaders** — position **DST** or **K** alone (ESPN scoring) |
| Open a leader in full profile | **Season Leaders** — click **Player** or **Team** name |
| Share a profile link | **Player Profile** — URL includes `?entity=` and `?season=` |
| Tune peer Z volume gates | `scripts/volume_report.py --season 2023` |

## Compare modes

| Mode | Use when |
|------|----------|
| **All-time** | Full careers in the database; seasons only one player played still show in the table |
| **Single season** | Same calendar year for both players (must overlap) |
| **Selected seasons** | Stats limited to the sidebar season window (one or many years; overlap not required) |

For multi-year compare, set sidebar **Season view** to **Season range** or **Pick seasons**, then choose **Selected seasons**.

## Commands

| Script | Purpose |
|--------|---------|
| `scripts/ingest_season.py` | Load seasons into DuckDB (`--season`, `--bulk --from-year` / `--to-year`) |
| `scripts/volume_report.py` | CLI check for peer-Z volume gates (`--season 2023`) |
| `scripts/rebuild_players.py` | Rebuild player search index from `season_stats` |
| `scripts/check_env.py` | Verify Python arch and package imports |

Resume a failed bulk ingest from a year:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_season.py --bulk --from-year 2001 --to-year 2025
```

## Configuration

| File | What it controls |
|------|------------------|
| [`src/scoring/presets.yaml`](src/scoring/presets.yaml) | Offensive scoring (Standard / Half-PPR / Full PPR) |
| [`src/scoring/kicker_presets.yaml`](src/scoring/kicker_presets.yaml) | ESPN kicker scoring |
| [`src/scoring/dst_presets.yaml`](src/scoring/dst_presets.yaml) | ESPN D/ST scoring |
| [`config/settings.yaml`](config/settings.yaml) | Default min games (8) |
| [`src/analytics/thresholds.yaml`](src/analytics/thresholds.yaml) | Volume gates for peer Z (WR/TE use targets) |
| [`.streamlit/config.toml`](.streamlit/config.toml) | Theme; `fileWatcherType = none` hides dev “File change” banner |

Re-ingest after schema or position-filter changes.

## Project layout

```
app/                    Streamlit UI (pages, charts, tables)
src/season_selection.py Sidebar season window helpers
src/scoring/            Fantasy point presets
src/analytics/          Z-scores, consistency, metrics
src/db/                 DuckDB schema, queries, maintenance
scripts/                Ingest and utilities
docs/                   Enhancement and multi-sport roadmaps
data/                   Local DuckDB (gitignored)
```

Planning docs: [docs/ENHANCEMENT_ROADMAP.md](docs/ENHANCEMENT_ROADMAP.md) (NFL polish, completed), [docs/MULTISPORT_ROADMAP.md](docs/MULTISPORT_ROADMAP.md) (MLB/NBA/NHL brainstorm).

## Troubleshooting

Run `.\.venv\Scripts\python.exe scripts\check_env.py` first — it flags 32-bit Python, missing packages, and DB presence.

| Issue | What to do |
|-------|------------|
| `python` not found / Store opens | Install 64-bit Python; use `py -3.14`; disable App execution aliases for `python.exe` |
| pandas build / Meson errors | Almost always **32-bit Python** — recreate venv with 64-bit and `pip install -r requirements.txt` |
| `Activate.ps1` blocked | Skip activation; use `.\.venv\Scripts\python.exe` for all commands (see Quick start) |
| Empty Season Leaders | Lower min games; re-ingest; sidebar **Repair database** |
| Missing **Opponent** in weekly table | Sidebar **Repair database**, or re-ingest that season |
| Player not in search | Type 2+ letters (e.g. `Luck`); **Repair database** or `scripts/rebuild_players.py` |
| Only two Compare modes | Choose **Selected seasons** (third mode is always listed); use multi-year sidebar window for span compare |
| Import / chart errors | `pip install -r requirements.txt` (includes matplotlib); clear `__pycache__` and restart Streamlit |

Expected ingest messages: `Dropped N weekly rows` (missing IDs or non-skill positions). Bulk ingest is **one season at a time** — safe to resume mid-range.

## License

MIT — see [LICENSE](LICENSE). NFL data via nflverse is CC-BY 4.0 (see nflverse docs).

## Contributing

PRs welcome. Before submitting:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
```
