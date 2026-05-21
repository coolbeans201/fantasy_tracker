# Fantasy Tracker

Open-source NFL fantasy analytics for **completed regular seasons** — season leaders, player careers, head-to-head compare, and Z-scores vs peers and career baselines.

Inspired by [NFL Perry](https://www.nflperry.com/) for data use cases, focused on historical analysis (not gameplay).

## Features

- **Scoring:** Standard, Half-PPR, Full PPR for offense; **ESPN default** for kickers and team D/ST
- **Season Leaders:** QB/RB/WR/TE/K plus **DST** (team defense units, e.g. Broncos), min games (default 8)
- **Player Profile:** Players (QB/RB/WR/TE/K) and team **D/ST** — career stats, FP chart, best week, peer/career Z
- **Compare:** All-time or single-season; search by name or team code (2+ characters)
- **Variance:** Z-score vs same-season peers; optional all-time position baseline

## Data

- [nflverse](https://github.com/nflverse) via [`nflreadpy`](https://nflreadpy.nflverse.com/)
- **1999+** regular seasons only; ingest ad-hoc when a season completes
- Players: **QB, RB, WR, TE, K**; team **D/ST** from nflverse team stats (see [`src/positions.py`](src/positions.py))

After upgrading to kickers / D/ST support, re-ingest seasons so new columns populate:

```bash
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

Database: `data/fantasy_tracker.duckdb` (gitignored). Use the **sidebar** for scoring preset, season, and min games.

## What you can do

| Question | Where |
|----------|--------|
| Who were the top half-PPR RBs in 2022 with at least 8 games? | **Season Leaders** — set season, position RB, scoring Half-PPR; adjust min games in sidebar |
| How does a player’s 2021 compare to their own career (strong/weak year for them)? | **Player Profile** — search player, check **Career Z** on the season row |
| How elite was a season vs other QBs/WRs that year? | **Player Profile** or **Season Leaders** — **Peer Z (season)**; enable **peer Z (all-time era)** in sidebar for a historical baseline |
| Compare Travis Kelce vs Mark Andrews in 2023 | **Compare** — search each name (2+ letters), mode **Single season**, pick 2023 in sidebar |
| Top ESPN-scoring defenses in 2022 | **Season Leaders** — position **DST**, min games 8 |
| Best kickers by field goals in 2023 | **Season Leaders** — position **K** (ESPN kicker scoring) |
| Compare two players’ full careers (totals and season-by-season) | **Compare** — mode **All-time** |
| See every stat we store for a player’s career or a single season | **Player Profile** — career table; expand **All career stats**; pick a season in sidebar for weekly/team splits |
| Broncos D/ST career and weekly scoring | **Player Profile** — search `DEN` or `DEN Defense` |
| Tune who counts for peer Z (targets, carries, etc.) | `scripts/volume_report.py --season 2023` (see [`src/analytics/thresholds.yaml`](src/analytics/thresholds.yaml)) |

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

Re-ingest after schema or position-filter changes.

## Project layout

```
app/              Streamlit UI
src/scoring/      Fantasy point presets
src/analytics/    Z-scores and volume thresholds
src/db/           DuckDB schema, queries, maintenance
scripts/          Ingest and utilities
data/             Local DuckDB (gitignored)
```

## Troubleshooting

Run `.\.venv\Scripts\python.exe scripts\check_env.py` first — it flags 32-bit Python, missing packages, and DB presence.

| Issue | What to do |
|-------|------------|
| `python` not found / Store opens | Install 64-bit Python; use `py -3.14`; disable App execution aliases for `python.exe` |
| pandas build / Meson errors | Almost always **32-bit Python** — recreate venv with 64-bit and `pip install -r requirements.txt` |
| `Activate.ps1` blocked | Skip activation; use `.\.venv\Scripts\python.exe` for all commands (see Quick start) |
| Empty Season Leaders | Restart Streamlit (backfills games from weekly rows); or lower min games in sidebar |
| Player not in search | Type 2+ letters (e.g. `Luck`); run `scripts/rebuild_players.py` if index looks thin |
| Import / chart errors | `pip install -r requirements.txt` (includes matplotlib for charts); clear `__pycache__` and restart |

Expected ingest messages: `Dropped N weekly rows` (missing IDs or non-skill positions). Bulk ingest is **one season at a time** — safe to resume mid-range.

## License

MIT — see [LICENSE](LICENSE). NFL data via nflverse is CC-BY 4.0 (see nflverse docs).

## Contributing

PRs welcome. Run `ruff check .` before submitting.
