# Handoff

## Current stage

Stage 0: Data-access discovery

Status: Complete

Decision: `GO`

## Completed

- Preserved the direct HTTP block evidence in ADR 0001.
- Verified the Hepsiburada homepage in a normal rendered browser.
- Used the visible site search to load a live `bebek arabası` listing.
- Confirmed live product cards expose title, URL, price, rating, evaluation count, and position.
- Opened one canonical product page and confirmed product attributes and provenance fields.
- Opened its public `-yorumlari` page and confirmed visible review text, dates, aggregate rating, distribution, and pagination.
- Confirmed that restricted `/api/` and `/product-comment/` endpoints are unnecessary.
- Recorded the browser-adapter decision in ADR 0002.

## Verified sample

- Search: `bebek arabası`
- Listing result: more than 10,000 products reported by the page
- Sample product: `Karf Momsafe Hamile Emniyet Kemeri Aparatı`
- Sample rating: 4.8
- Sample evaluation count: 115
- Visible reviews on first review page: 10
- Restricted endpoint calls: 0
- CAPTCHA or bypass attempts: 0

The sample values are discovery evidence only. They will not be shipped as seed or demo data.

## Implementation decision

Build a headed Playwright adapter that reads only rendered public DOM content. Keep concurrency at one, apply 6-12 second delays, use strict crawl limits, discard reviewer identity, and stop immediately on any access block.

## Next stage

Stage 1 is ready: create the Python project skeleton, configuration, database migration, CLI, health endpoint, and basic web shell.
