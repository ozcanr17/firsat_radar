# Handoff

## Read this first

This repository is the user's production market-research application. The user wants a cloud-hosted, continuously running system that can discover popular marketplace categories, inspect products and visible review evidence, compare commercial opportunities, and turn evidence into resale, sourcing, or local-production recommendations.

Communicate with the user in Turkish. Write clean code without code comments. At the end of every completed stage, update this file, commit to `main`, push to GitHub, wait for CI, and verify the Railway deployment. Never describe uncollected, simulated, or cached fixture data as live market evidence.

## Repository and production

- Repository: `https://github.com/ozcanr17/firsat_radar`
- Branch: `main`
- Release: `1.7.0`
- Last functional commit before this handoff: `b96b615`
- Railway panel: `https://firsatradar-production.up.railway.app/`
- Public GitHub Pages snapshot: `https://ozcanr17.github.io/firsat_radar/`
- Deployment guide: `docs/CLOUD_DEPLOYMENT.md`
- Project plan: `PROJECT_PLAN.md`
- Product brief: `PAZARRADAR.md`

The Railway service hosts the password-protected FastAPI panel, persistent SQLite database, Playwright browser runtime, and embedded scheduler. GitHub Pages is only a static public snapshot and cannot run the Python service, database, or bot.

## Current task

The immediate task is to make marketplace category targeting work correctly and evolve the system into a source-aware category traversal engine.

The triggering example is this Amazon Türkiye category URL:

`https://www.amazon.com.tr/gp/browse.html?node=12466208031&ref_=nav_em_ba_babyall_0_2_4_19`

The user expects an agent to accept a category URL, discover its subcategories, queue those subcategories, inspect products, enrich product details and visible reviews where permitted, and continue monitoring over time without needing the user's local computer.

## Completed work

### Cloud and interface

- Built the full FastAPI panel and bot for Railway with a persistent `/data` volume.
- Added HTTP Basic authentication for the cloud panel.
- Rebuilt `/` as the unified Radar Center.
- Added product, opportunity, commercial-recommendation, trade-desk, marketplace, run-history, and settings pages.
- Added the live agent state, queue state, category coverage, product observations, opportunity summaries, and manual `Şimdi tara` control to the Radar Center.
- Added a marketplace selector to the quick-target form.
- Added automatic marketplace detection when a URL is pasted.
- Verified the desktop UI and Amazon URL auto-detection in the in-app browser.

### Scheduler and collection

- The embedded scheduler starts a guarded cycle at service startup and then repeats hourly.
- A cycle processes up to three due watch targets and three round-robin catalog pages.
- Collection is sequential, delayed by 6–12 seconds, and capped at 800 external requests per UTC day.
- Non-overlap protection, retry handling, a circuit breaker, raw-evidence retention, backups, review analysis, and opportunity analysis run in the same pipeline.
- Direct Hepsiburada product targets can be discovered, persisted, refreshed, and linked back to their watch targets.
- Structured product-page price, old price, rating, review count, image, product details, and already-visible review evidence are persisted with provenance.
- Product refreshes create new snapshots and retain prior listing values when structured product data omits a field.

### Marketplace-aware targets

- Fixed the bug where the Radar Center always submitted `source_name: "hepsiburada"`, which caused Amazon URLs to fail with `invalid_marketplace_url`.
- Amazon category URLs now preserve the allowlisted `node` parameter and discard tracking parameters such as `ref_`.
- Amazon product targets validate ASINs from `/dp/{ASIN}` and `/gp/product/{ASIN}` paths.
- The watchlist monitor now has a source-aware crawler registry rather than assuming one crawler for every target.
- `ListingResult` now carries normalized child-category links.
- Permitted Hepsiburada category pages can extract same-marketplace child-category links.
- Child targets are URL-deduplicated, queued with lower priority, limited to 40 links per page, and limited to a configurable six-level traversal depth.
- Category-only landing pages can expand into child targets even when they contain no product cards.
- The new settings are `FIRSAT_RADAR_CATEGORY_DISCOVERY_LINKS_PER_PAGE` and `FIRSAT_RADAR_CATEGORY_DISCOVERY_MAX_DEPTH`.

### Verification

- Ruff lint: passed.
- Ruff format: passed.
- Mypy strict mode: passed.
- Pytest: 58 tests passed.
- CLI doctor: passed.
- GitHub Actions run `30662885573`: passed.
- Railway served the new deployment after commit `b96b615`.
- The production `/healthz` endpoint returned HTTP 200 with a healthy database.
- The worktree was clean and synchronized with `origin/main` before this handoff update.

## Current blockers

### Amazon Türkiye is registered but intentionally inactive

Amazon browse targets can now be saved and retain their browse-node identity, but they are not automatically crawled. `MARKETPLACES` currently marks `amazon_tr` as `credentials_required`, so `watch_target_view()` sets `refresh_due` to false for Amazon targets.

This is deliberate. Amazon's published terms exclude product-list, description, and price collection through robots, data mining, or similar extraction tools from the granted license. Do not activate a public-page Amazon crawler, circumvent restrictions, or imply that a visible page grants permission.

The approved implementation path is Amazon Creators API or explicit written automation permission. Creators API requires Amazon Associates acceptance and generated credentials. Relevant official documentation:

- `https://affiliate-program.amazon.com/creatorsapi/docs/en-us/onboarding/register-for-creators-api`
- `https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference`
- `https://affiliate-program.amazon.com/creatorsapi/docs/en-us/api-reference/resources`

No Amazon credential has been provided. Do not ask the user to paste secrets into chat or commit them. Credentials must be stored as Railway environment variables after the connector defines exact variable names.

### Hepsiburada is blocked from the current Railway egress IP

The production Playwright session received a Hepsiburada security page while requesting `robots.txt`. The collector stopped correctly and did not bypass it.

At the last verification, `/healthz` reported:

- `scheduler_status`: `circuit_open`
- `consecutive_failures`: `2`
- `circuit_open_until`: `2026-08-01T20:02:00Z`, which is `2026-08-01 23:02` in Europe/Istanbul

The circuit state came from the earlier Hepsiburada source failure and is stored in the persistent database. Do not reset the circuit merely to force another blocked request. First confirm that the source policy endpoint is reachable and allowed from the runtime.

### The circuit breaker is global

One source failure can currently block the whole scheduled pipeline. This will become incorrect once multiple marketplace connectors are active. A Hepsiburada failure must not prevent a permitted Amazon API or approved feed connector from running.

### The user's Amazon target may still need to be re-added

The original `invalid_marketplace_url` request failed before persistence. The user should hard-refresh the live Radar Center, choose `Kategori`, paste the Amazon Baby URL, and submit it again. The expected result is a saved Amazon target with a `credentials_required` state, not an active crawl.

## Next implementation plan

### Stage 15A: Source-isolated runtime controls

1. Replace the single global collection circuit with per-source circuit state.
2. Ensure a blocked Hepsiburada connector cannot stop other permitted connectors.
3. Expose each source's last run, next retry, policy state, and error reason in the marketplace UI.
4. Keep a small global circuit only for application-wide database or scheduler failures.
5. Add integration tests covering one failed source and one successful source in the same cycle.

### Stage 15B: Official Amazon Creators API connector

1. Verify current official Creators API authentication, Turkish marketplace locale support, rate limits, browse-node operations, search operations, and available product resources.
2. Add explicit Railway settings for Credential ID, Credential Secret, credential version, partner tag, and marketplace locale.
3. Implement OAuth token acquisition and bounded retry/throttling behavior without logging secrets.
4. Implement `GetBrowseNodes` for the category hierarchy.
5. Implement `SearchItems` for products in each browse node.
6. Implement `GetItems` only for the product resources needed by the common evidence model.
7. Register the Amazon crawler in `build_pipeline()` only when configuration is complete.
8. Change the marketplace state dynamically from `credentials_required` to `active` only after a successful authenticated health check.
9. Do not invent review text if Creators API does not provide reviews. Store explicit unavailability reason codes and keep review-derived scores disabled for that source.
10. Add contract tests with recorded, redacted fixtures and an opt-in live smoke test that makes the smallest possible API request.

### Stage 15C: Commercial usefulness

1. Add cross-market product identity using GTIN/EAN, brand, model, normalized title, and confidence-scored matching.
2. Build category briefs showing demand, price bands, seller concentration, review pain clusters, margin scenarios, and data confidence.
3. Add durable notifications for material price moves, rising products, repeated complaint clusters, and margin-qualified opportunities.
4. Separate resale, wholesale sourcing, and local-production recommendations.
5. Require explicit evidence, costs, risks, and a validation plan before showing `GO`.
6. Integrate approved Trendyol and MediaMarkt feeds only after access agreements or official connector credentials exist.

## Important architecture locations

- `app/config.py`: runtime settings and safety limits
- `app/bootstrap.py`: production crawler and scheduler assembly
- `app/scheduler.py`: guarded scheduled pipeline and global circuit behavior
- `app/services/crawl.py`: generic crawl persistence and child-category target creation
- `app/services/watchlist.py`: source-aware watch-target routing
- `app/services/commerce.py`: marketplace URL normalization and watch-target validation
- `app/services/marketplaces.py`: connector definitions and access states
- `app/sources/base.py`: source adapter protocol
- `app/sources/hepsiburada/browser.py`: rendered browser adapter and category-link discovery
- `app/sources/hepsiburada/parser.py`: product and category normalization
- `app/sources/amazon_tr/parser.py`: current ASIN parser; this is not yet an API connector
- `app/web/templates/dashboard.html`: Radar Center quick-target UI and URL auto-detection
- `app/web/templates/marketplaces.html`: connector status page
- `tests/integration/test_crawl.py`: persistence, product refresh, watchlist, and category traversal tests
- `tests/integration/test_scheduler.py`: pipeline and circuit behavior tests
- `tests/integration/test_web.py`: panel and API behavior tests

## Pitfalls encountered

- The quick-target JavaScript hardcoded Hepsiburada even when the user pasted an Amazon URL. Source selection must always come from an explicit form value or verified hostname detection.
- Generic URL canonicalization removed every query parameter. That destroyed Amazon's `node` category identity. Query normalization must use per-source allowlists, not an all-or-nothing rule.
- A category landing page can contain subcategory links without product cards. Treating zero product cards as immediate parser drift prevented traversal before child links were persisted.
- The first child-category bound was 12, but the user's visible Amazon Baby category already had more branches. Traversal limits must be configurable and large enough for the visible taxonomy while remaining bounded.
- The original crawler and product linker assumed Hepsiburada globally. New code must resolve source, external identity extraction, policy URL, and adapter through a connector registry.
- A global circuit breaker is acceptable for a one-source prototype but becomes a cross-market outage in a multi-source system.
- GitHub Pages cannot host FastAPI, SQLite, Playwright, or an always-on scheduler. The static Pages snapshot and the Railway control plane must never be conflated.
- Railway can serve stale artifacts briefly while a deployment is building. Verify both GitHub Actions success and an observable new Railway artifact before declaring a release live.
- Browser-visible data is not automatically licensed for automated commercial collection. Technical accessibility and authorization are separate gates.

## Never do these again

- Never bypass robots rules, HTTP 403/429, CAPTCHA, security interstitials, login controls, or marketplace access restrictions.
- Never add proxy rotation, stealth evasion, fingerprint spoofing, hidden/private endpoint use, or CAPTCHA-solving automation.
- Never claim Amazon, Trendyol, or MediaMarkt collection is active when only a target record or connector placeholder exists.
- Never hardcode a source name in a multi-market form, service, product linker, or scheduler path.
- Never strip required marketplace identity parameters such as Amazon `node`; preserve only explicit per-source allowlists and remove tracking parameters.
- Never launch unbounded recursive traversal. Deduplicate URLs, cap breadth and depth, apply source rate limits, and process through a persistent queue.
- Never let one source's policy or security failure silently stop every other source.
- Never fabricate review content, ratings, demand, price history, opportunity evidence, or commercial recommendations.
- Never publish raw reviewer identities or secrets.
- Never commit `.env`, Railway credentials, runtime databases, raw evidence, browser profiles, backups, watch targets, or business cases.
- Never weaken tests or safety gates merely to make a live crawl appear successful.
- Never reset the production circuit repeatedly against a known security block.
- Never finish a stage without updating `HANDOFF.md`, running the full quality suite, committing `main`, pushing, and checking the deployment.

## Required verification commands

Run from the repository root:

```bash
.venv/bin/ruff check app tests alembic
.venv/bin/ruff format --check app tests alembic
.venv/bin/mypy app tests
.venv/bin/pytest
.venv/bin/python -m app.cli doctor
git diff --check
git status --short --branch
```

For delivery:

```bash
git push origin main
gh run list --branch main --limit 3
curl -sS https://firsatradar-production.up.railway.app/healthz
```

Do not run destructive Git commands against the user's worktree. Preserve unrelated user changes if the worktree is not clean.
