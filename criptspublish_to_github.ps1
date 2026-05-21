[33mcommit 17c9b96607f180925ab4f79ca9da9e8ad6804cf9[m[33m ([m[1;36mHEAD[m[33m -> [m[1;32mmain[m[33m)[m
Author:     coolbeans201 <matthewben5@aol.com>
AuthorDate: Thu May 21 10:25:02 2026 -0400
Commit:     coolbeans201 <matthewben5@aol.com>
CommitDate: Thu May 21 10:25:02 2026 -0400

    Initial commit: Fantasy Tracker v0.1.0
    
    Open-source NFL fantasy analytics for completed regular seasons (1999+),
    built with Python, Streamlit, DuckDB, and nflverse data via nflreadpy.
    
    Data pipeline
    - Ingest nflverse weekly player stats (REG only) into DuckDB
    - Skill positions only: QB, RB (HB/FB -> RB), WR, TE
    - Full display names (player_display_name) with master-file backfill
    - Season and per-team aggregates; games played from distinct weeks
    - Scoring presets: Standard, Half-PPR, Full PPR (configurable YAML)
    - Bulk ingest one season at a time with resume-friendly manifest
    - DB maintenance: games backfill, players index rebuild, name refresh
    
    Streamlit app
    - Season Leaders: filters, readable stat labels, combined Fumbles Lost,
      peer Z (season + optional all-time era), CSV export
    - Player Profile: fuzzy search (2+ chars), career table, matplotlib FP chart,
      career Z vs personal baseline, team splits and weekly detail
    - Compare: all-time or single-season head-to-head with readable stat labels
    - Sidebar: scoring preset, season, min games (default 8)
    
    Analytics
    - Peer Z vs same-season qualified peers (position volume gates; WR/TE targets)
    - Career Z vs player's own career mean/std
    - Volume report CLI for threshold tuning
    
    Utilities
    - check_env.py, rebuild_players.py, volume_report.py
    - Unit tests for scoring, positions, games played, display labels, players table
    
    Docs: README with quick start, example workflows, compact troubleshooting
