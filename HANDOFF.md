# Handoff

## Current stage

Stage 13: Unified Radar Center and continuous discovery

Status: Complete

Release: 1.6.0

## Delivered

- Rebuilt `/` as the single operational Radar Center.
- Added live agent, queue, category coverage, product, opportunity, and run visibility to one page.
- Added **Şimdi tara** for an authenticated, non-overlapping background cycle.
- Added quick Hepsiburada product and category target registration.
- Added eight prioritized popular-category cards with enable and disable controls.
- Added `/api/v1/radar`, `/api/v1/radar/run`, category state, and circuit reset endpoints.
- Enabled the 17-category round-robin catalog by default.
- Changed the scheduler to start immediately and then repeat hourly.
- Changed each cycle to process both due watch targets and category discovery.
- Bounded the fallback discovery request to the collector's 60-product safety limit.
- Added direct discovery for unresolved Hepsiburada product URLs.
- Linked newly discovered products back to their watch targets.
- Added bounded category target discovery.
- Added structured product-page price, rating, review-count, and image extraction.
- Added a new product snapshot on every tracked product refresh.
- Preserved the previous listing values when product structured data omits a field.
- Kept analysis, retention, backup, non-overlap, circuit breaker, quota, and policy gates in the same cycle.

## Operating model

1. Railway starts the authenticated FastAPI service and migrates the persistent database.
2. The embedded scheduler queues an immediate guarded cycle, then runs hourly.
3. Up to three due watch targets are discovered or refreshed.
4. Three pages from prioritized category agents are scanned in round-robin order.
5. Visible product facts and reviews are persisted as evidence.
6. Opportunity and review analysis runs after collection.
7. The Radar Center shows the new state and allows an additional manual cycle.

The unified control page is `https://firsatradar-production.up.railway.app/`. Detailed pages remain available for products, opportunities, recommendations, profitability, marketplaces, runs, and settings.

## Access boundary

- Hepsiburada uses public rendered pages without private APIs.
- Public visibility is not interpreted as unrestricted permission.
- Every navigation is checked against cached source policy.
- Requests remain sequential with a 6–12 second interval and an 800 request daily cap.
- The collector stops on policy denial, HTTP 403, HTTP 429, CAPTCHA, security pages, and parser drift.
- No proxy rotation, hidden API, authentication bypass, CAPTCHA bypass, or access-control bypass is implemented.
- Amazon Türkiye, Trendyol, and MediaMarkt remain inactive until official credentials or approved feeds are connected.

## Verification

- Ruff lint passed.
- Ruff format passed.
- Mypy strict mode passed.
- Pytest passed: 53 tests.
- Desktop Radar Center layout was visually verified in the in-app browser.
- Mobile Radar Center layout was visually verified at 390 × 844.
- Product URL discovery and watch-target linking are covered by integration tests.
- Watchlist and catalog execution in the same scheduler cycle are covered by integration tests.
- Radar status and category management APIs are covered by integration tests.
- Railway accepted release `1.6.0`, but Hepsiburada returned a security page for `robots.txt` from the Railway egress IP during the first live catalog probe. The collector stopped without bypassing it.

## Delivery

- Repository: `https://github.com/ozcanr17/firsat_radar`
- Cloud panel: `https://firsatradar-production.up.railway.app/`
- Public snapshot: `https://ozcanr17.github.io/firsat_radar/`
- Cloud guide: `docs/CLOUD_DEPLOYMENT.md`

Runtime databases, raw evidence, browser state, credentials, watch targets, and business cases remain outside Git.

## Next stage

Stage 14 should add durable notification channels, cross-market product identity, official Amazon Creators API ingestion, approved Trendyol and MediaMarkt feeds, category-level trend briefs, and acquisition or local-production validation workflows.
