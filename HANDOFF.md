# Handoff

## Current stage

Stage 12: Cloud control plane and multi-market foundation

Status: Complete

Release: 1.5.1

## Delivered

- Added a production Docker image with Playwright Chromium.
- Added Railway configuration for GitHub deployments, health checks, one replica, and a persistent `/data` volume.
- Added automatic migrations and an optional embedded hourly scheduler to the FastAPI lifecycle.
- Added password protection for every panel and API route except `/healthz` and static assets.
- Added `/marketplaces` as the marketplace connection control center.
- Registered Hepsiburada, Amazon Türkiye, Trendyol, and MediaMarkt Türkiye with explicit collection modes and access states.
- Added `/api/v1/marketplaces` for connector visibility.
- Extended watch targets with a marketplace source and safe per-domain URL normalization.
- Allowed the Esnaf Masası to record products or categories from all registered marketplaces.
- Added schema migration `20260731_0009`.
- Removed the Anne & Bebek-only restriction from product selection in the Esnaf Masası.
- Added the Railway environment template and cloud deployment guide.
- Added a Railway volume entrypoint that repairs mounted `/data` ownership before dropping privileges to the `radar` user.

## Cloud operating model

1. Railway builds the repository Dockerfile whenever `main` changes.
2. The FastAPI panel migrates the database and starts behind a required administrator password.
3. A single embedded scheduler prioritizes due watch targets every hour.
4. Runtime data, evidence, watch targets, and business cases persist on `/data`.
5. GitHub Pages remains the public read-only snapshot; the Railway URL is the private operational panel.
6. The service must remain at one replica while SQLite and the embedded scheduler share a volume.

The cloud service is fully prepared but cannot receive a public URL until the owner creates the Railway project, attaches `/data`, and sets the administrator password. These are account and secret operations that cannot be committed to a public repository.

## Marketplace access

- Hepsiburada: existing visible-browser collector, policy gate, bounded rate, and stop conditions.
- Amazon Türkiye: connector contract is identified as Creators API; credentials and account eligibility are required.
- Trendyol: official Marketplace Partner API manages seller operations and is not treated as an unrestricted full-market catalog API; an approved catalog or affiliate feed is required.
- MediaMarkt Türkiye: an approved catalog or affiliate feed is required before automated collection is marked active.

Targets can already be registered for every marketplace. Unsupported sources remain visibly blocked and are not silently crawled.

## Delivery

- Public snapshot: `https://ozcanr17.github.io/firsat_radar/`
- Repository: `https://github.com/ozcanr17/firsat_radar`
- Cloud panel: `https://firsatradar-production.up.railway.app/`
- Cloud instructions: `docs/CLOUD_DEPLOYMENT.md`
- Cloud configuration: `railway.toml`, `Dockerfile`, `.env.railway.example`

Runtime SQLite, marketplace credentials, watch targets, business cases, policy files, cached pages, and raw review evidence remain outside Git under `data/` or cloud secrets.

## Verification

- Ruff lint passed.
- Ruff format check passed.
- Mypy strict mode passed.
- Pytest passed: 48 tests.
- Production Docker image built successfully.
- Container `/healthz` returned HTTP 200.
- Container `/marketplaces` returned HTTP 401 without credentials and HTTP 200 with valid credentials.
- No external product page was requested during this stage.

## Safety contract

- One browser connection with 6–12 seconds between external requests.
- Hard limit of 800 requests per UTC day.
- No hidden API, query-pagination abuse, proxy rotation, CAPTCHA bypass, or access-control bypass.
- Stop on policy denial, HTTP 403, HTTP 429, CAPTCHA, security page, or parser drift.
- Credentials stay in cloud secrets and never enter Git.
- Market scores and profitability calculations remain validation aids, not guarantees.

## Next stage

Stage 13 connects official or approved marketplace data sources. Amazon requires Creators API credentials. Trendyol and MediaMarkt require approved catalog or affiliate feeds. After the first second-market source is active, add cross-market product matching, price dispersion, category briefs, and opportunity ranking across sources.
