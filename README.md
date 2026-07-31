# Firsat Radar

Firsat Radar is a local-first product opportunity research application planned around traceable, permitted e-commerce data.

## Current status

Stage 3 is complete. The application performs a policy-gated, single-tab browser crawl of the public Hepsiburada Anne, Bebek, Oyuncak listing, enriches a strictly limited product set, and stores identity-minimized public reviews without restricted endpoints.

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

Check the current policy and run a limited live crawl:

```bash
.venv/bin/python -m app.cli policy-check --source hepsiburada
.venv/bin/python -m app.cli crawl --source hepsiburada --limit-products 20
.venv/bin/python -m app.cli crawl --source hepsiburada --limit-products 5 --limit-details 2
```

The browser runs visibly, uses one tab, and stops on an access block or CAPTCHA. Each requested detail includes only its first public rendered review page. Reviewer identity is discarded before persistence, and direct contact identifiers in review text are redacted.

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
