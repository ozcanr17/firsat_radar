# Firsat Radar

Firsat Radar is a local-first product opportunity research application planned around traceable, permitted e-commerce data.

## Current status

Stage 2 is complete. The application performs a policy-gated, single-tab browser crawl of the public Hepsiburada Anne, Bebek, Oyuncak listing and persists real products, provenance, and snapshots without restricted endpoints.

See [ADR 0002](docs/adr/0002-browser-data-access.md) and [HANDOFF.md](HANDOFF.md) for evidence and next steps.

## Requirements

- Python 3.12
- Google Chrome

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install --no-deps -e .
cp .env.example .env
.venv/bin/python -m app.cli init-db
```

## Run

Check the current policy and run a limited live listing crawl:

```bash
.venv/bin/python -m app.cli policy-check --source hepsiburada
.venv/bin/python -m app.cli crawl --source hepsiburada --limit-products 20
```

The browser runs visibly, uses one tab, and stops on an access block or CAPTCHA. Product detail and review collection remain disabled until Stage 3.

Start the local application:

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

The application does not include seed, demo, or fabricated market data. Live results always retain their source URL, observation time, fetch provenance, coverage, and confidence.
