# Handoff

## Current stage

Stage 9: Search and commercial decision support

Status: Complete

Release: 1.2.0

## Delivered

- Added case-insensitive product and brand search over collected live products.
- Added category filtering and rank, recency, review count, price, and opportunity sorting.
- Added a dedicated Commercial Recommendations navigation item and page.
- Added evidence-gated `Al-sat adayı`, `Yerel üretim adayı`, `Yakından izle`, `Şimdilik uzak dur`, and `Önce veri topla` routes.
- Added readiness, confidence, evidence, risks, and three concrete validation steps to every recommendation.
- Added explicit margin, logistics, returns, tax, regulation, certification, and missing-detail warnings where applicable.
- Added at most two product-detail and first-page public-review enrichments per category page.
- Increased local scheduled analysis capacity to 200 products per job.
- Prioritized products without a current analysis before already analyzed products to prevent starvation as the catalog grows.
- Added recommendation methodology documentation.

## Current operating state

- The web panel is running locally at `http://127.0.0.1:8001` for acceptance.
- The scheduler is not running automatically with the web panel.
- Continuous market monitoring requires a separate foreground `schedule` process.
- Default frequency: hourly.
- Default scheduled scope: three category pages, up to two product details per page, and up to 200 local analyses.

## Run

```bash
.venv/bin/python -m app.cli open-panel
.venv/bin/python -m app.cli schedule
```

The commands must run in separate terminals.

## Live acceptance

- Product search: `Macbook`
- Category filter: `Bilgisayar, Tablet`
- Sort: public review count
- Matching live products: 2
- Recommendation results after initial catalog analysis: 39
- Initial routes: 1 al-sat candidate, 38 research-required
- Bounded detail acceptance: 1 category page, 36 products, 2 details, 19 new redacted reviews
- Recommendation results after enrichment and backlog analysis: 73
- Routes after enrichment: 3 al-sat candidates, 70 research-required
- Local-production candidates: 0 because current pain evidence does not satisfy the minimum gate
- Access blocks or CAPTCHA: none

## Verification

- Search and filter UI visually verified with collected live products.
- Commercial Recommendations UI visually verified.
- Recommendation cards expose evidence, risk, and next validation steps.
- Ruff lint passed.
- Ruff format check passed.
- Mypy strict mode passed.
- Pytest passed: 38 tests.

## Safety contract

- Recommendations are research priorities, not guarantees of demand, profit, or production feasibility.
- Low-confidence or low-coverage products remain `Önce veri topla` rather than receiving speculative commercial advice.
- Runtime market data remains ignored under `data/` and is not committed.
- Collection remains visible, sequential, single-tab, robots-gated, and rate-limited to 6-12 seconds.
- Crawls stop on HTTP 403, HTTP 429, CAPTCHA, access blocks, policy denial, or parser drift.
- No access bypass, proxy rotation, hidden API, `/api/`, or `/product-comment/` collection is used.
- Reviewer identity minimization and direct-contact redaction remain active.

## Next stage

Stage 10 should add operator-defined watchlists and a dedicated product-freshness queue. This will let the operator request a product/category focus and repeatedly refresh stale, changed, high-review-count, high-momentum, or high-opportunity products without waiting for a complete category sweep.
