# Handoff

## Current stage

Stage 8: Continuous catalog monitoring

Status: Complete

Release: 1.1.0

## Delivered

- Added 17 verified public top-level Hepsiburada categories.
- Added persistent category cursors with next page, learned page size, page count, sweep count, last product signature, last status, and timestamps.
- Added bounded round-robin traversal so every category advances fairly across scheduled jobs.
- Added `?sayfa=N` pagination without hidden APIs or background endpoints.
- Added repeated-page and short-terminal-page detection before restarting a category sweep.
- Added hourly scheduling with three category pages per job by default.
- Kept every scheduled batch behind the existing process lock, backup, retry, circuit breaker, retention, robots, and access-block controls.
- Added category-aware product persistence instead of assigning every product to the original category.
- Added catalog progress to the Settings panel.
- Added `catalog-seed`, `catalog-status`, `catalog-run`, and confirmed `catalog-reset` commands.
- Added migrations `20260731_0006` and `20260731_0007`.

## How it works

1. The category queue selects the least recently crawled enabled category.
2. The bot checks robots policy for the exact category page.
3. A visible Chrome session opens one page and reads rendered product cards.
4. Products and snapshots are persisted with category, source URL, fetch, timestamp, coverage, and confidence.
5. The category cursor advances without losing progress when the process stops.
6. A short or repeated terminal page completes the category sweep and resets it to page one.
7. The next scheduled job continues with the least recently crawled category.
8. Analysis updates opportunity evidence from the accumulated market history.

## Run continuously

Run the panel and scheduler in separate terminals:

```bash
.venv/bin/python -m app.cli open-panel
.venv/bin/python -m app.cli schedule
```

Inspect progress:

```bash
.venv/bin/python -m app.cli catalog-status
.venv/bin/python -m app.cli runtime-status
```

## Acceptance

- Public category directory visually inspected at low volume.
- `?sayfa=2` verified on a public category page with visible product cards.
- Live catalog migration completed through `20260731_0007`.
- 17 category cursors created.
- Live one-page catalog run completed without detail or review requests.
- 36 visible products processed on the accepted category page.
- Corrected page-size learning after the live page exposed a 36-product rendered page size.
- Cursor acceptance after correction: one page scanned, zero false sweep completions, next category selected fairly.
- Ruff lint passed.
- Ruff format check passed.
- Mypy strict mode passed.
- Pytest passed: 37 tests.

## Safety contract

- Runtime market data remains ignored under `data/` and is not committed.
- Collection remains visible, sequential, single-tab, and rate-limited to 6–12 seconds between requests.
- Each scheduled job is bounded to three category pages by default.
- Crawls stop on robots denial, HTTP 403, HTTP 429, CAPTCHA, access blocks, or parser drift.
- No access bypass, proxy rotation, hidden API, `/api/`, or `/product-comment/` collection is used.
- An instantaneous complete-market guarantee is not claimed; coverage accumulates over successive safe sweeps.
- Reviewer identity minimization and direct-contact redaction remain active for later detail refreshes.

## Known limits and next stage

- Main categories are covered, but automatic subcategory graph discovery is not yet implemented.
- Broad catalog traversal currently collects listing snapshots; it does not refresh every product detail and review page.
- At the safe default rate, a full sweep can take days or weeks and the catalog may change during the sweep.
- Stage 9 should add a separate freshness queue that prioritizes stale, changed, high-review-count, high-momentum, and high-opportunity products for detail and public-review refresh.
