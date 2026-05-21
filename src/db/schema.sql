-- Fantasy Tracker DuckDB schema

CREATE TABLE IF NOT EXISTS ingest_manifest (
    season INTEGER PRIMARY KEY,
    ingested_at TIMESTAMP NOT NULL,
    row_count INTEGER
);

CREATE TABLE IF NOT EXISTS players (
    player_id VARCHAR PRIMARY KEY,
    player_name VARCHAR NOT NULL,
    position VARCHAR,
    last_season INTEGER
);

CREATE TABLE IF NOT EXISTS weekly_stats (
    player_id VARCHAR NOT NULL,
    player_name VARCHAR,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    season_type VARCHAR NOT NULL,
    team VARCHAR,
    position VARCHAR,
    games INTEGER,
    passing_completions DOUBLE DEFAULT 0,
    passing_attempts DOUBLE DEFAULT 0,
    passing_yards DOUBLE DEFAULT 0,
    passing_tds DOUBLE DEFAULT 0,
    interceptions DOUBLE DEFAULT 0,
    sacks_suffered DOUBLE DEFAULT 0,
    carries DOUBLE DEFAULT 0,
    rushing_yards DOUBLE DEFAULT 0,
    rushing_tds DOUBLE DEFAULT 0,
    rushing_fumbles_lost DOUBLE DEFAULT 0,
    receptions DOUBLE DEFAULT 0,
    targets DOUBLE DEFAULT 0,
    receiving_yards DOUBLE DEFAULT 0,
    receiving_tds DOUBLE DEFAULT 0,
    receiving_fumbles_lost DOUBLE DEFAULT 0,
    fumbles_lost DOUBLE DEFAULT 0,
    fantasy_points_standard DOUBLE,
    fantasy_points_half_ppr DOUBLE,
    fantasy_points_full_ppr DOUBLE,
    PRIMARY KEY (player_id, season, week, season_type, team)
);

CREATE TABLE IF NOT EXISTS season_team_stats (
    player_id VARCHAR NOT NULL,
    player_name VARCHAR,
    season INTEGER NOT NULL,
    team VARCHAR NOT NULL,
    position VARCHAR,
    games INTEGER,
    passing_completions DOUBLE DEFAULT 0,
    passing_attempts DOUBLE DEFAULT 0,
    passing_yards DOUBLE DEFAULT 0,
    passing_tds DOUBLE DEFAULT 0,
    interceptions DOUBLE DEFAULT 0,
    sacks_suffered DOUBLE DEFAULT 0,
    carries DOUBLE DEFAULT 0,
    rushing_yards DOUBLE DEFAULT 0,
    rushing_tds DOUBLE DEFAULT 0,
    rushing_fumbles_lost DOUBLE DEFAULT 0,
    receptions DOUBLE DEFAULT 0,
    targets DOUBLE DEFAULT 0,
    receiving_yards DOUBLE DEFAULT 0,
    receiving_tds DOUBLE DEFAULT 0,
    receiving_fumbles_lost DOUBLE DEFAULT 0,
    fumbles_lost DOUBLE DEFAULT 0,
    fantasy_points_standard DOUBLE,
    fantasy_points_half_ppr DOUBLE,
    fantasy_points_full_ppr DOUBLE,
    PRIMARY KEY (player_id, season, team)
);

CREATE TABLE IF NOT EXISTS season_stats (
    player_id VARCHAR NOT NULL,
    player_name VARCHAR,
    season INTEGER NOT NULL,
    position VARCHAR,
    teams VARCHAR,
    games INTEGER,
    passing_completions DOUBLE DEFAULT 0,
    passing_attempts DOUBLE DEFAULT 0,
    passing_yards DOUBLE DEFAULT 0,
    passing_tds DOUBLE DEFAULT 0,
    interceptions DOUBLE DEFAULT 0,
    sacks_suffered DOUBLE DEFAULT 0,
    carries DOUBLE DEFAULT 0,
    rushing_yards DOUBLE DEFAULT 0,
    rushing_tds DOUBLE DEFAULT 0,
    rushing_fumbles_lost DOUBLE DEFAULT 0,
    receptions DOUBLE DEFAULT 0,
    targets DOUBLE DEFAULT 0,
    receiving_yards DOUBLE DEFAULT 0,
    receiving_tds DOUBLE DEFAULT 0,
    receiving_fumbles_lost DOUBLE DEFAULT 0,
    fumbles_lost DOUBLE DEFAULT 0,
    fantasy_points_standard DOUBLE,
    fantasy_points_half_ppr DOUBLE,
    fantasy_points_full_ppr DOUBLE,
    best_week INTEGER,
    best_week_fp DOUBLE,
    best_week_scoring VARCHAR,
    PRIMARY KEY (player_id, season)
);

CREATE INDEX IF NOT EXISTS idx_weekly_season ON weekly_stats(season);
CREATE INDEX IF NOT EXISTS idx_season_pos ON season_stats(season, position);
CREATE INDEX IF NOT EXISTS idx_season_team ON season_team_stats(season, team);
