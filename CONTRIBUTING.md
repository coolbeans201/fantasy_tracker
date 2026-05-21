# Contributing to Fantasy Tracker

Thanks for helping improve Fantasy Tracker.

## Setup

```bash
pip install -e ".[dev]"
```

## Ingest test data

```bash
python scripts/ingest_season.py --season 2023
```

## Lint

```bash
ruff check .
ruff format .
```

## Pull requests

- Keep changes focused and match existing Python style.
- Update README if you add user-facing features or new ingest options.
- Do not commit `data/*.duckdb` or large generated files.
