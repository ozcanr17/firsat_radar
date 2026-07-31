# Handoff

## Current stage

Stage 10: PazarRadar v2 and GitHub delivery

Status: Complete

Release: 1.3.0

## Delivered

- Adopted the supplied PazarRadar v2 Anne & Bebek scope as the current product contract.
- Disabled legacy query-pagination catalog scheduling by default.
- Added a hard 800-request UTC daily quota and an honest project user agent.
- Added a polished, searchable, responsive static research panel for GitHub Pages.
- Restricted the public snapshot to Anne & Bebek products and aggregate commercial evidence.
- Added a static export command and safe empty-state coverage.
- Added GitHub Actions for CI, Pages deployment, and a guarded manual market bot.
- Added a public delivery and source-access ADR.

## Source-access decision

- Cached robots content advertises product and category sitemap indexes.
- A direct bounded sitemap acceptance attempt on 2026-07-31 returned a Hepsiburada security page instead of XML.
- External collection stopped immediately; no bypass was attempted.
- The hosted bot remains manual-only and performs policy-check, cached analysis, and publishing without product-page collection.
- Recurring collection must not be enabled until a policy-gated sitemap attempt returns valid XML.

## Delivery

- Public panel: `https://ozcanr17.github.io/firsat_radar/`
- Repository: `https://github.com/ozcanr17/firsat_radar`
- Local panel: `.venv/bin/python -m app.cli open-panel`
- Static export: `.venv/bin/python -m app.cli export-site --output public`

The tracked `site/` snapshot contains derived product facts and recommendations only. Runtime SQLite, cached pages, policy files, and raw review evidence remain ignored under `data/`.

## Verification

- Ruff lint passed.
- Ruff format check passed.
- Mypy strict mode passed.
- Pytest passed: 40 tests.
- Pip dependency check passed.
- Static export completed with three Anne & Bebek products and three recommendations.

## Safety contract

- One browser connection with 6–12 seconds between external requests.
- Hard limit of 800 requests per UTC day.
- No query pagination, `/product-comment/`, hidden API, proxy rotation, or bypass behavior.
- Stop on policy denial, HTTP 403, HTTP 429, CAPTCHA, security page, or parser drift.
- No reviewer identity or direct contact information is published.
- Recommendations require validation and do not guarantee demand, profit, or production feasibility.

## Next stage

Stage 11 must validate a sitemap as XML without bypass behavior, add sitemap-first discovery for baby strollers, high chairs, and bottle/pacifier products, and produce category-level commercial briefs. Until then, use the public panel as a research snapshot and the local app for operator review.
