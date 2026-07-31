# Firsat Radar

Firsat Radar is a local-first product opportunity research application planned around traceable, permitted e-commerce data.

## Current status

Stage 6 is complete. The application provides the responsive research panel plus non-overlapping scheduling, bounded retry, circuit breaking, verified SQLite backups, raw-evidence retention, and persistent operational state.

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
.venv/bin/python -m app.cli analyze --limit-products 60
.venv/bin/python -m app.cli backup
.venv/bin/python -m app.cli prune-raw --dry-run
.venv/bin/python -m app.cli runtime-status
```

The browser runs visibly, uses one tab, and stops on an access block or CAPTCHA. Each requested detail includes only its first public rendered review page. Reviewer identity is discarded before persistence, and direct contact identifiers in review text are redacted.

Start the local application:

```bash
.venv/bin/python -m app.cli serve
```

Open `http://127.0.0.1:8000`. Do not open `app/web/templates/index.html` directly: Jinja templates and static assets are rendered only through the running FastAPI application. The health endpoint is available at `http://127.0.0.1:8000/healthz`.

The live APIs are available at `http://127.0.0.1:8000/api/v1/products` and `http://127.0.0.1:8000/api/v1/opportunities`. Opportunity results include metric evidence, coverage, confidence, risks, and an explicitly validation-required hypothesis.

The panel pages are available at `/`, `/products`, `/products/{id}`, `/opportunities`, `/runs`, and `/settings`. CSV exports are available at `/exports/products.csv` and `/exports/opportunities.csv`.

Run the scheduler as a separate local process with `.venv/bin/python -m app.cli schedule`. See [Operations](docs/operations.md) before enabling it.

## Checks

```bash
.venv/bin/ruff check app tests alembic
.venv/bin/ruff format --check app tests alembic
.venv/bin/mypy app tests
.venv/bin/pytest
.venv/bin/python -m app.cli doctor
```

The application does not include seed, demo, or fabricated market data. Live results always retain their source URL, observation time, fetch provenance, coverage, and confidence.
