# Handoff

## Current stage

Stage 5: Web interface

Status: Complete

## Completed

- Replaced the operational table page with a complete responsive research panel.
- Added a persistent dark navigation shell, live system status, and local API links.
- Added a dashboard with live product, review, opportunity, and crawl-run totals.
- Added opportunity spotlight cards with score, confidence, evidence, and risk counts.
- Added a full live product catalog with price, rating, public reviews, stored reviews, detail coverage, and opportunity score.
- Added product evidence pages with source link, current values, opportunity metrics, hypothesis, risks, description, attributes, provenance, snapshot history, and identity-minimized review evidence.
- Added a complete opportunity ranking page with five metric bars and risk badges.
- Added crawl-run history with status, products, details, reviews, fetches, and error codes.
- Added a read-only settings page with access limits, policy controls, and correct local run instructions.
- Added UTF-8 CSV exports for products and opportunities.
- Added local timezone rendering for UTC database timestamps.
- Added a self-contained favicon and no external UI dependencies.
- Added desktop and 390-pixel responsive layouts.
- Added explicit guidance not to open Jinja template files directly.
- Corrected a Turkish lexical false positive where `geç` matched inside `vazgeçilmezim`.
- Added stale review-label cleanup and analysis model `rules-tr-v2`.

## Available panel routes

- `/`: dashboard overview
- `/products`: live product catalog
- `/products/{id}`: product evidence page
- `/opportunities`: opportunity ranking
- `/runs`: crawl provenance history
- `/settings`: safe runtime configuration and run instructions
- `/exports/products.csv`: product export
- `/exports/opportunities.csv`: opportunity export
- `/api/v1/products`: product JSON API
- `/api/v1/opportunities`: opportunity JSON API

## Correct local usage

```bash
.venv/bin/python -m app.cli serve
```

Open `http://127.0.0.1:8000`. Opening `app/web/templates/index.html` directly shows raw Jinja expressions and does not load the application context.

## Live verification

- Dashboard: HTTP 200 with live data
- Product catalog: HTTP 200
- Product evidence page: HTTP 200
- Opportunity ranking: HTTP 200
- Crawl history: HTTP 200
- Settings: HTTP 200
- Product CSV: HTTP 200
- Opportunity CSV: HTTP 200
- Desktop visual verification: passed
- 390-pixel mobile visual verification: passed
- Live products displayed: 3
- Live reviews displayed: 20
- Latest opportunity model: `rules-tr-v2`
- Stale labels corrected: 3

## Verification

- Ruff lint: passed
- Ruff format check: passed
- Mypy strict mode: passed
- Pytest: 25 passed
- Static stylesheet route: passed
- All panel route integration checks: passed
- CSV content checks: passed
- No Python code comments: passed

## Known limits

- The panel is local and does not include authentication or remote deployment.
- Settings are intentionally read-only; environment variables remain the source of truth.
- Product filtering, search, and pagination are deferred until the live catalog exceeds the current hard limit of 60.
- Scheduling, retention, backups, and circuit-breaker operations remain inactive.

## Next stage

Stage 6 is ready: add non-overlapping scheduling, bounded retries, circuit breaker, raw-evidence retention, SQLite backups, operational status, and recovery documentation.
