# Handoff

## Read this first

This repository is the user's production market-research application. The user wants a cloud-hosted, continuously running system that can discover popular marketplace categories, inspect products and visible evidence, compare commercial opportunities, and turn evidence into resale, sourcing, or local-production recommendations.

Communicate with the user in Turkish. Write clean code without code comments. At the end of every completed stage, update this file, commit to `main`, push to GitHub, wait for CI, and verify the Railway deployment. Never describe uncollected, simulated, or cached fixture data as live market evidence.

## Repository and production

- Repository: `https://github.com/ozcanr17/firsat_radar`
- Branch: `main`
- Release: `1.8.0`
- Railway panel: `https://firsatradar-production.up.railway.app/`
- Public GitHub Pages snapshot: `https://ozcanr17.github.io/firsat_radar/`
- Deployment guide: `docs/CLOUD_DEPLOYMENT.md`
- Project plan: `PROJECT_PLAN.md`
- Product brief: `PAZARRADAR.md`

The Railway service hosts the password-protected FastAPI panel, persistent SQLite database, Playwright browser runtime, and embedded scheduler. GitHub Pages is only a static public snapshot and cannot run the Python service, database, or bot.

## Current state: the radar now collects real market data

Before this stage the application had no working data source in production. Hepsiburada was blocked, and every other connector was a placeholder. The system could not find anything.

It now collects live, permitted market evidence from two working sources and derives opportunities from it.

### Verified working sources

`vatan` — Vatan Bilgisayar, a Turkish retailer on its own infrastructure.

- Plain HTTPS with a self-identifying bot user agent, no browser required.
- `robots.txt` grants `User-agent: *` access to category and product pages.
- Product pages publish complete schema.org `Product` JSON-LD: price, availability, brand, rating, review count, SKU, and **MPN**. MPN is the key for cross-market product identity in Stage 16.
- Verified live: policy allowed, 24 products parsed per category page, full pipeline run created 12 products, 12 snapshots, 12 analyses and opportunities.

`akakce` — Akakçe, a price-comparison engine.

- Same permitted plain-HTTP approach.
- Product pages publish schema.org `ProductGroup` with `AggregateOffer`: `offerCount`, `lowPrice`, `highPrice`, and per-seller price, availability, seller name, and the real destination marketplace URL.
- This yields genuine **cross-marketplace price spread from a single permitted source**, without crawling Hepsiburada or Trendyol directly. Verified real example: the same MacBook Air listed at `37.999,00 TL` on Hepsiburada and `45.839,05 TL` on Pttavm — a 17.1% spread across three marketplaces, scored as `price_arbitrage` with the offer evidence attached.
- Listing pages expose `data-pr` (product id) and `data-cp` (seller count).

Both sources were reached with an honest `FirsatRadar/1.8` user agent. Nothing is spoofed.

### Real opportunity scoring

The scoring model is now `rules-tr-v3`. It adds a `spread` metric computed from observed merchant offers:

- `spread = (highest_offer - lowest_offer) / highest_offer * 100`, only when at least two offers exist.
- Pattern `price_arbitrage` fires at `spread >= 12%`.
- Reasons carry the concrete evidence: lowest offer, highest offer, offer count, marketplace names.
- Risks include `single_offer_no_spread` and `spread_within_single_marketplace` so a one-seller observation is never presented as an arbitrage finding.
- Weights were rebalanced so that when `spread` is absent the remaining five metrics keep exactly their previous relative ratios. Historic scores are unchanged apart from one 0.01 float rounding difference.
- Coverage treats "fewer than two offers" as *not applicable* rather than *missing*, so single-seller retailers are not unfairly penalised.

### Stage 15A completed: per-source circuit isolation

The global circuit breaker no longer stops every source.

- New table `source_runtime_state` with per-source status, consecutive failures, circuit window, last error, last run, and last success.
- `MultiSourceCollector` (`app/services/collection.py`) runs each source independently. A failure opens only that source's circuit; an open circuit skips only that source.
- The overall cycle reports `completed` when at least one source succeeded, so analysis still runs.
- Rate limiting is treated as backpressure, not a fault: `_rate_limited`, `_rate_limit_cooldown`, and `daily_quota_reached` mark the source `throttled` **without** incrementing failures or opening the circuit.
- `WatchlistMonitor` and `CatalogMonitor` are both source-scoped now. `CatalogMonitor` queries filter by `source_id`, and a `paginated=False` profile keeps sources whose robots.txt forbids pagination on page 1.
- Per-source state is shown on `/marketplaces` with status, last successful scan, circuit window, and error code.

This was verified live, not just in tests: in a real pipeline run Akakçe was blocked and opened its own circuit while Vatan completed successfully and the cycle still produced 12 analyses.

### Politeness and safety

- Per-source delays: Vatan 15–25s, Akakçe 25–45s, each with its own persisted last-request timestamp.
- Per-source daily quotas: Vatan 500, Akakçe 400.
- `RateLimitCooldown` persists a backoff window and honours `Retry-After`.
- HTTP 403 is a hard block; 429 is a throttle with cooldown; challenge interstitials (`Just a moment...`) engage the cooldown and stop.
- Robots policy is generic and per-source (`app/sources/robots.py`), cached per source.

## Current blockers

### Akakçe is behind Cloudflare and is currently challenged

While validating seed category URLs I sent roughly thirty requests in a short window and tripped Cloudflare. Akakçe now returns a `Just a moment...` interstitial for HTML pages from this IP, while `robots.txt` still returns 200.

The collector detects this and stops. **Do not attempt to solve, bypass, or evade the challenge.** The correct response is to wait; the per-source circuit and cooldown already handle it. The delays were raised to 25–45s specifically because of this.

It is not yet confirmed whether Railway's egress IP is challenged. Check `/marketplaces` after deployment: if `akakce` shows `circuit_open` with `listing_access_denied`, it is challenged there too, and Vatan carries the system until it clears.

### Hepsiburada is blocked at the network edge, not just from Railway

The previous handoff attributed this to the Railway egress IP. That was wrong. `https://www.hepsiburada.com/robots.txt` returns **HTTP 403 from an ordinary residential IP as well**. The block is not Railway-specific.

`FIRSAT_RADAR_HEPSIBURADA_ENABLED` now defaults to `false`. Its Playwright path also needs a headed browser, which Railway cannot provide. Leave it disabled unless a permitted access route appears.

### Amazon Türkiye remains intentionally inactive

Amazon browse targets are saved and retain their browse-node identity but are not crawled. `MARKETPLACES` marks `amazon_tr` as `credentials_required`.

This is deliberate. Amazon's terms exclude product-list, description, and price collection through robots or similar extraction tools. Do not activate a public-page Amazon crawler or imply that a visible page grants permission. The approved path is the Creators API with Associates credentials stored as Railway environment variables. No credential has been provided.

## Next implementation plan

### Stage 16: cross-market product identity

1. Match products across sources using MPN, GTIN/EAN, brand, and normalized title with a confidence score. Vatan already supplies MPN and SKU; Akakçe supplies brand and a normalized title.
2. Persist an identity cluster so the same physical product from Vatan and from an Akakçe merchant offer resolves to one entity.
3. Compute spread across *sources*, not only within one Akakçe page. This is the largest remaining unlock: it turns two independent feeds into a genuine arbitrage table.

### Stage 17: category briefs and notifications

1. Category briefs: demand, price bands, seller concentration (`seller_count` is already collected), and data confidence.
2. Durable notifications for material price moves, new arbitrage spreads, and margin-qualified opportunities.
3. Separate resale, wholesale sourcing, and local-production recommendations, each requiring explicit evidence, costs, risks, and a validation plan before showing `GO`.

### Stage 18: additional permitted sources

1. Cimri was verified reachable and permitted (`robots.txt` 200, category pages 200 with an honest bot UA) but has no adapter yet. It is a comparison engine like Akakçe and would add redundancy.
2. Amazon Creators API once credentials exist.
3. Trendyol and MediaMarkt only after access agreements.

## Important architecture locations

- `app/config.py`: runtime settings, per-source delays, quotas, enablement flags
- `app/bootstrap.py`: per-source crawler registry, catalog profiles, pipeline assembly
- `app/scheduler.py`: guarded scheduled pipeline and global circuit behavior
- `app/services/collection.py`: **per-source isolation and circuit routing**
- `app/services/source_state.py`: per-source runtime state
- `app/services/crawl.py`: generic crawl persistence, merchant offers, child-category targets
- `app/services/catalog.py`: source-scoped category cursors and seed profiles
- `app/services/watchlist.py`: source-aware watch-target routing
- `app/services/marketplaces.py`: connector definitions, access states, runtime status
- `app/analysis/scoring.py`: `rules-tr-v3` including the spread metric
- `app/sources/robots.py`: generic per-source robots policy
- `app/sources/throttle.py`: rate limiter, daily quota, rate-limit cooldown
- `app/sources/http_source.py`: shared permitted-HTTP adapter base
- `app/sources/vatan/`: Vatan parser and adapter
- `app/sources/akakce/`: Akakçe parser and adapter
- `tests/integration/test_collection.py`: per-source circuit isolation tests

## Pitfalls encountered

- The previous handoff's diagnosis that Hepsiburada was blocked "from the Railway egress IP" was not verified. It returns 403 from a residential IP too. Always reproduce a network claim before designing around it.
- Validating seed URLs with a fast loop tripped Cloudflare on Akakçe and cost hours of usable access. Probe third-party sites at the same rate the production collector uses, not faster.
- `Accept: text/html` alone makes some servers return HTTP 406 for `robots.txt`. Include `text/plain`.
- A 429 is not a permanent block. Treating it as one opened a 24-hour circuit on a source that would have recovered in minutes. Rate limits are backpressure and need their own state.
- Vatan renders two `.product-list__content` blocks per product; only one holds the anchor. Resolve the link from the card *or its ancestor*, and do not count deduplicated repeats as parse failures — that pushed coverage to 0.71, barely above the drift threshold, for a page that parsed perfectly.
- JSON-LD inside `<script>` is not entity-decoded by the HTML parser. Unescape it explicitly, or titles keep `&quot;`.
- A module-level `import html` collides with a parameter named `html`. Import `unescape` directly.
- Adding a sixth scoring metric changes every historic score unless the weights are chosen so the remaining metrics keep their prior ratios after renormalization.
- `CatalogMonitor` originally queried `CategoryCursor` with no source filter. Any second source silently shared and corrupted the first source's cursor state.
- Browser-visible data is not automatically licensed for automated commercial collection. Technical accessibility and authorization are separate gates.

## Never do these again

- Never bypass robots rules, HTTP 403/429, CAPTCHA, security interstitials, login controls, or marketplace access restrictions.
- Never add proxy rotation, stealth evasion, fingerprint spoofing, hidden/private endpoint use, or CAPTCHA-solving automation.
- Never claim a marketplace is being collected when only a target record or connector placeholder exists.
- Never hardcode a source name in a multi-market form, service, product linker, catalog, or scheduler path.
- Never strip required marketplace identity parameters such as Amazon `node`.
- Never launch unbounded recursive traversal. Deduplicate URLs, cap breadth and depth, apply source rate limits, and process through a persistent queue.
- Never let one source's policy or security failure stop every other source.
- Never fabricate review content, ratings, demand, price history, opportunity evidence, or commercial recommendations.
- Never publish raw reviewer identities or secrets.
- Never commit `.env`, Railway credentials, runtime databases, raw evidence, browser profiles, backups, watch targets, or business cases.
- Never weaken tests or safety gates merely to make a live crawl appear successful.
- Never probe a third-party site faster than the production collector would.
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
