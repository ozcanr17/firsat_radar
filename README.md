# Firsat Radar

Firsat Radar is a local-first product opportunity research application planned around traceable, permitted e-commerce data.

## Current status

Stage 1 is complete. The repository contains the Python application skeleton, environment configuration, full initial SQLite schema, Alembic migration, CLI, health endpoint, and an explicit `NO_DATA` web state.

See [ADR 0002](docs/adr/0002-browser-data-access.md) and [HANDOFF.md](HANDOFF.md) for evidence and next steps.

## Requirements

- Python 3.12

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install --no-deps -e .
cp .env.example .env
.venv/bin/python -m app.cli init-db
```

## Run

```bash
.venv/bin/python -m app.cli serve
```

Open `http://127.0.0.1:8000`. The health endpoint is available at `http://127.0.0.1:8000/healthz`.

## Checks

```bash
.venv/bin/ruff check app tests alembic
.venv/bin/ruff format --check app tests alembic
.venv/bin/mypy app tests
.venv/bin/pytest
.venv/bin/python -m app.cli doctor
```

No live crawl is implemented yet. The application does not include seed, demo, or fabricated market data.
