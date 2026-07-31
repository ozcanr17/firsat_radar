# Handoff

## Current stage

Stage 2: Live listing slice

Status: Complete

## Completed

- Added a browser-based robots policy gate with a 24-hour local cache.
- Added a persistent per-domain 6-12 second navigation limiter across CLI processes.
- Added a headed, single-tab Chrome adapter for rendered public listing pages.
- Added security-block, HTTP 403, HTTP 429, CAPTCHA, timeout, and parser-drift stop states.
- Added resilient product-card projection and Turkish price, rating, review-count, URL, and external-ID normalization.
- Added the 70 percent parser coverage gate.
- Added compressed raw evidence storage with content hashes.
- Added source, run, fetch, product, snapshot, and optional delivery persistence.
- Added idempotent product upsert and duplicate-content short-circuiting.
- Added `policy-check` and limited `crawl` CLI commands.
- Added `GET /api/v1/products` with provenance, coverage, and confidence.
- Updated the dashboard to display live products or the explicit `NO_DATA` state.
- Added migration `20260731_0002` for product image URLs.

## Live verification

- Policy state: `allowed`
- Robots response: HTTP 200 through the rendered browser
- Target: `https://www.hepsiburada.com/anne-bebek-oyuncak-c-2147483639`
- Listing pages requested: 1
- Product limit: 3
- Products created: 3
- Snapshots created: 3
- Fetch provenance records: 2
- Parser coverage: 100 percent
- Restricted endpoint calls: 0
- CAPTCHA or bypass attempts: 0
- Final migration: `20260731_0002`

The live data remains under the ignored `data/` directory and is not committed as application data.

## Verification

- Ruff lint: passed
- Ruff format check: passed
- Mypy strict mode: passed
- Pytest: 15 passed
- Clean migration chain: passed
- Live `/healthz`: HTTP 200
- Live `/api/v1/products`: returned persisted products
- Live dashboard: `LIVE_DATA`

## Current commands

```bash
.venv/bin/python -m app.cli policy-check --source hepsiburada
.venv/bin/python -m app.cli crawl --source hepsiburada --limit-products 20
.venv/bin/python -m app.cli serve
```

## Known limits

- Product details and public review pages are not collected yet.
- Listing discovery is limited to the first rendered category page.
- Browser selectors are versioned but currently cover one observed layout.
- Scheduling and analysis remain inactive.

## Next stage

Stage 3 is ready: enrich a strictly limited product set from canonical pages and collect visible public reviews with coverage and reason codes while discarding reviewer identity.
