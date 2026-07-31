# Handoff

## Current stage

Stage 11: Operator trade desk and watchlist refresh

Status: Complete

Release: 1.4.0

## Delivered

- Added the local Esnaf Masası at `/trade-desk`.
- Added persistent product/category watch targets with priority and refresh intervals.
- Added a freshness queue combining operator priority, data age, opportunity score, and unresolved discovery state.
- Added direct, policy-gated refresh for due products already known to the catalog.
- Made the hourly scheduler prioritize up to three due watchlist products.
- Removed separate review-page navigation; only reviews already visible on the opened product page are classified.
- Added review pain clusters with frequency and high-severity counts.
- Added persisted unit economics: purchase, commission, shipping, packaging, advertising, returns, tax, other cost, target margin, and volume.
- Added contribution, net margin, return on cost, break-even price, target sale price, monthly contribution, and strict GO/NO-GO decisions.
- Connected unit economics to recommendation evidence and risks.
- Added a non-persisting profitability calculator to the public GitHub Pages panel.
- Added watchlist and commerce JSON APIs.
- Added schema migration `20260731_0008`.
- Recorded the safe optional AI decision boundary in ADR 0004.

## Operating model

1. Add a known product or category hypothesis in Esnaf Masası.
2. Keep `.venv/bin/python -m app.cli schedule` running separately from the web panel.
3. The scheduler refreshes due products sequentially under policy, quota, rate, and circuit-breaker controls.
4. Run or wait for deterministic analysis.
5. Enter real costs before acting on a recommendation.
6. Treat only aligned market evidence and positive unit economics as an actionable test candidate.

Unresolved product URLs wait for sitemap discovery. They are never converted into blind category browsing or query pagination.

## Source-access decision

- A bounded sitemap acceptance attempt on 2026-07-31 returned a Hepsiburada security page instead of XML.
- No bypass was attempted and hosted recurring collection remains disabled.
- The GitHub bot checks policy, analyzes cached permitted data, and publishes without product-page collection.
- Sitemap-first category discovery remains blocked until a policy-gated endpoint returns valid XML.

## Delivery

- Public panel: `https://ozcanr17.github.io/firsat_radar/`
- Repository: `https://github.com/ozcanr17/firsat_radar`
- Local panel: `.venv/bin/python -m app.cli open-panel`
- Local scheduler: `.venv/bin/python -m app.cli schedule`
- One-time watch refresh: `.venv/bin/python -m app.cli watchlist-refresh --limit 3`
- Static export: `.venv/bin/python -m app.cli export-site --output public`

Runtime SQLite, watch targets, business cases, policy files, cached pages, and raw review evidence remain ignored under `data/`.

## Verification

- Ruff lint passed.
- Ruff format check passed.
- Mypy strict mode passed.
- Pytest passed: 45 tests.
- Pip dependency check passed.
- Esnaf Masası desktop layout was visually verified against the migrated local database.
- Public profitability calculator produced the expected live GO result.
- No live external product request was made during this stage.

## Safety contract

- One browser connection with 6–12 seconds between external requests.
- Hard limit of 800 requests per UTC day.
- No query pagination, `/product-comment/`, separate review-page navigation, hidden API, proxy rotation, CAPTCHA bypass, or access-control bypass.
- Stop on policy denial, HTTP 403, HTTP 429, CAPTCHA, security page, or parser drift.
- No reviewer identity or direct contact information is published.
- Market scores and profitability calculations remain validation aids, not guarantees.

## Next stage

Stage 12 must validate sitemap XML, implement sitemap-first discovery for baby strollers, high chairs, and bottle/pacifier products, and generate category commercial briefs. An optional model-assisted brief layer can then be added after API credentials are configured; deterministic evidence and unit economics remain the authority.
