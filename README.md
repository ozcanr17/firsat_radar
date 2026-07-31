# PazarRadar

PazarRadar is a cloud-ready, evidence-driven market research and unit-economics application. It combines permitted marketplace data, review evidence, opportunity scoring, watch targets, and real cost scenarios.

## Public panel

The read-only research panel is published at [ozcanr17.github.io/firsat_radar](https://ozcanr17.github.io/firsat_radar/). It contains product facts, aggregate signals, recommendation evidence, risks, and validation steps. It does not publish raw reviews or reviewer information.

GitHub Pages serves the static snapshot in `site/`. The full password-protected FastAPI panel, background bot, and persistent SQLite database are packaged for Railway and no longer require a local computer after deployment.

## Cloud panel

The repository contains a production Docker image, Railway configuration, automatic database migrations, an embedded hourly scheduler, persistent `/data` storage support, and HTTP Basic authentication. Follow [the cloud deployment guide](docs/CLOUD_DEPLOYMENT.md) once to connect the repository to Railway. Every later push to `main` is deployed from GitHub.

Production domain: [firsatradar-production.up.railway.app](https://firsatradar-production.up.railway.app/)

The cloud panel opens on the unified Radar Center. It starts a guarded scan, registers product or category targets, shows the live agent state, manages popular category agents, and links to products, opportunities, recommendations, profitability, marketplaces, runs, and settings. Marketplace credentials and feed agreements are stored only as cloud secrets; they are never committed to GitHub.

## Requirements

- Python 3.12
- Google Chrome

## Local setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install --no-deps -e .
cp .env.example .env
.venv/bin/python -m app.cli init-db
```

Start the local panel:

```bash
.venv/bin/python -m app.cli open-panel
```

The command upgrades the database and opens `http://127.0.0.1:8000`. The panel pages are `/`, `/products`, `/products/{id}`, `/opportunities`, `/recommendations`, `/trade-desk`, `/marketplaces`, `/runs`, and `/settings`. Products support text, category, and sort filters.

Use `/trade-desk` to add product or category watch targets and calculate real profitability. The calculation includes purchase cost, commission, shipping, packaging, advertising, return provision, tax provision, other variable costs, target margin, and monthly volume. It returns contribution, net margin, return on cost, break-even price, target sale price, monthly contribution, and a strict `GO` or `NO-GO` result.

## Safe collection

Always check policy before a bounded collection:

```bash
.venv/bin/python -m app.cli policy-check --source hepsiburada
.venv/bin/python -m app.cli crawl --source hepsiburada --limit-products 20 --limit-details 2
.venv/bin/python -m app.cli analyze --limit-products 200
.venv/bin/python -m app.cli watchlist-refresh --limit 3
.venv/bin/python -m app.cli export-site --output public
```

Collection is visible, single-tab, sequential, delayed by 6–12 seconds, and capped at 800 external requests per UTC day. It stops on policy denial, HTTP 403, HTTP 429, CAPTCHA, security pages, or parser drift. It does not use query pagination, hidden APIs, `/product-comment/`, separate review-page navigation, proxy rotation, or bypass behavior. Review evidence is extracted only when already visible on the opened product page.

The hourly scheduler starts its first cycle when the cloud service boots. Every cycle processes up to three due watch targets, rotates through three category pages, analyzes collected evidence, applies retention, and records operational state. A new Hepsiburada product URL is opened directly, converted into a tracked product, and linked to its watch target. An allowed category page can create up to 12 deduplicated child-category targets per visit, with a maximum traversal depth of three levels.

The Radar Center recognizes marketplace URLs. Amazon Türkiye browse targets preserve the safe `node` parameter and remove tracking parameters, so `gp/browse.html?node=...` links can be registered without an `invalid_marketplace_url` error. Amazon targets remain paused until Creators API credentials or written automation permission is connected. The application does not turn a registered URL into permission to operate a public-page robot.

The collector uses only publicly rendered pages that pass the source policy gate. Public visibility does not remove a marketplace's terms, robots rules, or technical access controls. The system never promises permission-free access and stops instead of bypassing a restriction.

## GitHub Actions

- `Quality checks` runs lint, formatting, typing, tests, and dependency checks on every push and pull request to `main`.
- `Deploy public research panel` publishes `site/` to GitHub Pages after relevant changes and can be run manually.
- `Run guarded market bot` is manual-only. It checks source policy, analyzes cached permitted data, and republishes the snapshot. It does not collect product pages until sitemap XML acceptance and sitemap-first discovery are implemented.

GitHub Actions does not impersonate a marketplace crawler. Full collection runs in the password-protected cloud service and remains subject to every source's access policy. The public panel includes a browser-side profitability calculator that does not transmit or persist entered values.

## Verification

```bash
.venv/bin/ruff check app tests alembic
.venv/bin/ruff format --check app tests alembic
.venv/bin/mypy app tests
.venv/bin/pytest
.venv/bin/python -m app.cli doctor
docker build -t firsat-radar .
```

See [PazarRadar v2](PAZARRADAR.md), [ADR 0003](docs/adr/0003-pazarradar-v2-and-github-delivery.md), [ADR 0004](docs/adr/0004-ai-decision-boundary.md), and [HANDOFF.md](HANDOFF.md) for the current scope, access decision, and AI boundary.
