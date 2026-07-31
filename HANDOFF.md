# Handoff

## Current stage

Stage 3: Product detail and reviews

Status: Complete

## Completed

- Added a policy check before every product-detail and public-review navigation.
- Added single-tab rendered detail enrichment with the existing persistent 6-12 second limiter.
- Added title, canonical URL, brand, seller, visible description, attributes, origin, overseas-sale, stock, and review-URL extraction.
- Added field coverage, confidence, and explicit missing-field reason codes.
- Added migration `20260731_0003` and product-detail provenance snapshots.
- Added first-page public review collection from the visible `-yorumlari` page.
- Excluded reviewer names, initials, avatars, profiles, and locations from the collection projection.
- Added deterministic review hashes and product-level idempotency.
- Added direct e-mail, phone, and 11-digit identifier redaction from review text.
- Stored identity-redacted review evidence instead of the original review-page HTML.
- Added detail coverage, detail confidence, and stored-review count to the product API and dashboard.
- Enabled the bounded `--limit-details` CLI option with the hard maximum of 20.

## Live verification

- Policy state: `allowed`
- Listing pages requested: 1
- Product limit: 2
- Detail limit: 2
- Public review pages: 2 total, one per product
- Products seen: 2
- Product details created: 2
- Public reviews created: 20
- Fetch provenance records: 6
- Detail coverage: 100 percent for both products
- Detail confidence: 100 percent for both products
- Missing-field reason codes: none
- Direct identifier scan matches: 0
- Restricted endpoint calls: 0
- CAPTCHA or bypass attempts: 0
- Final migration: `20260731_0003`

The live data remains under the ignored `data/` directory and is not committed as application data.

## Verification

- Ruff lint: passed
- Ruff format check: passed
- Mypy strict mode: passed
- Pytest: 18 passed
- Clean migration chain: passed
- Live `/healthz`: HTTP 200
- Live `/api/v1/products`: HTTP 200 with detail coverage and stored review counts
- Live dashboard: HTTP 200 with `LIVE_DATA`

## Current commands

```bash
.venv/bin/python -m app.cli policy-check --source hepsiburada
.venv/bin/python -m app.cli crawl --source hepsiburada --limit-products 20
.venv/bin/python -m app.cli crawl --source hepsiburada --limit-products 5 --limit-details 2
.venv/bin/python -m app.cli serve
```

## Known limits

- Only the first rendered category page is discovered.
- Only the first public rendered review page is collected for each enriched product.
- Review-level star ratings are unavailable in the observed visible DOM and remain null.
- Browser selectors currently cover one observed product and review layout.
- Review evidence is identity-redacted at collection time; automated retention starts in Stage 6.
- Analysis and scheduling remain inactive.

## Next stage

Stage 4 is ready: implement price and review metrics, rule-based Turkish review labels, opportunity scoring, evidence-backed reason codes, and coverage-aware confidence.
