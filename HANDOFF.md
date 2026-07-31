# Handoff

## Current stage

Stage 7: Acceptance and delivery

Status: Complete

Release: 1.0.0

## Delivered

- Added a polished responsive dashboard with products, opportunities, product evidence, run history, settings, JSON APIs, and CSV exports.
- Separated the server-rendered dashboard from the directly opened `index.html` file.
- Replaced the raw Jinja direct-file experience with a polished static panel launcher.
- Added `open-panel` to upgrade the database, start the service, and open the correct local URL.
- Made `serve` apply pending migrations before accepting requests.
- Preserved traceable live data, coverage, confidence, source URLs, fetch provenance, and review-identity minimization.
- Preserved robots gating, sequential single-tab navigation, bounded requests, access-block stops, scheduling locks, circuit breaking, verified backups, and raw-evidence retention.

## Start

```bash
.venv/bin/python -m app.cli open-panel
```

The panel opens at `http://127.0.0.1:8000`.

## Final acceptance

- Desktop panel visually verified through the running HTTP application.
- Direct `index.html` statically verified to contain no Jinja expressions or statements.
- Dashboard, products, product detail, opportunities, runs, settings, health, both JSON APIs, and both CSV exports returned HTTP 200.
- Clean Python 3.12 environment installed from `requirements.lock`.
- Clean database migrated through revisions `20260731_0001` to `20260731_0005`.
- Clean-environment doctor and dependency checks passed.
- Ruff lint passed.
- Ruff format check passed.
- Mypy strict mode passed.
- Pytest passed: 33 tests.
- Repository audit passed: no tracked runtime data, caches, environment files, secrets, demo market data, fabricated market data, or code comments.
- Git whitespace validation passed.

## Live smoke test

- Policy state: `allowed`
- Policy response: HTTP 200
- Crawl limit: 1 product
- Detail limit: 0
- Run status: `completed`
- Products seen: 1
- Existing products updated: 1
- Snapshots created: 1
- Detail or review requests: 0
- Access blocks or CAPTCHA: none

## Safety contract

- Runtime market data remains ignored under `data/` and is not committed.
- The application contains no seed, demo, or fabricated market data.
- Public rendered pages are accessed visibly, sequentially, and through one tab.
- Crawls stop on robots denial, HTTP 403, HTTP 429, CAPTCHA, or parser drift.
- No access bypass, proxy rotation, hidden API, `/api/`, or `/product-comment/` collection is used.
- Reviewer identity is discarded and direct contact identifiers are redacted before persistence.
- Opportunity output remains a validation-required hypothesis backed by evidence, coverage, confidence, and risks.

## Operational commands

```bash
.venv/bin/python -m app.cli doctor
.venv/bin/python -m app.cli policy-check --source hepsiburada
.venv/bin/python -m app.cli crawl --source hepsiburada --limit-products 20
.venv/bin/python -m app.cli analyze --limit-products 60
.venv/bin/python -m app.cli backup
.venv/bin/python -m app.cli prune-raw --dry-run
.venv/bin/python -m app.cli runtime-status
.venv/bin/python -m app.cli scheduled-run
.venv/bin/python -m app.cli schedule
```

## Known limits

- The application is local-first and has no remote deployment or authentication layer.
- The scheduler remains a separate foreground process rather than a macOS launch agent.
- Source markup changes can require parser maintenance and intentionally stop collection.
- Marketplace terms and robots policy must be rechecked before expanding collection scope.
