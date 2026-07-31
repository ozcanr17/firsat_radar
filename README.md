# PazarRadar

PazarRadar is an evidence-driven Anne & Bebek opportunity research and unit-economics application for permitted, traceable Hepsiburada data.

## Public panel

The read-only research panel is published at [ozcanr17.github.io/firsat_radar](https://ozcanr17.github.io/firsat_radar/). It contains product facts, aggregate signals, recommendation evidence, risks, and validation steps. It does not publish raw reviews or reviewer information.

GitHub Pages serves the static snapshot in `site/`. The full FastAPI application and SQLite database remain local.

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

The command upgrades the database and opens `http://127.0.0.1:8000`. The panel pages are `/`, `/products`, `/products/{id}`, `/opportunities`, `/recommendations`, `/trade-desk`, `/runs`, and `/settings`. Products support text, category, and sort filters.

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

The hourly local scheduler prioritizes up to three due products from the watchlist. Unresolved URLs wait for sitemap discovery. The legacy category scheduler is disabled because it does not satisfy the current sitemap-first scope.

## GitHub Actions

- `Quality checks` runs lint, formatting, typing, tests, and dependency checks on every push and pull request to `main`.
- `Deploy public research panel` publishes `site/` to GitHub Pages after relevant changes and can be run manually.
- `Run guarded market bot` is manual-only. It checks source policy, analyzes cached permitted data, and republishes the snapshot. It does not collect product pages until sitemap XML acceptance and sitemap-first discovery are implemented.

Hosted collection is intentionally not scheduled while advertised sitemap endpoints return a Hepsiburada security page. A valid XML acceptance result is required before enabling recurring GitHub collection. The public panel includes a browser-side profitability calculator that does not transmit or persist entered values.

## Verification

```bash
.venv/bin/ruff check app tests alembic
.venv/bin/ruff format --check app tests alembic
.venv/bin/mypy app tests
.venv/bin/pytest
.venv/bin/python -m app.cli doctor
```

See [PazarRadar v2](PAZARRADAR.md), [ADR 0003](docs/adr/0003-pazarradar-v2-and-github-delivery.md), [ADR 0004](docs/adr/0004-ai-decision-boundary.md), and [HANDOFF.md](HANDOFF.md) for the current scope, access decision, and AI boundary.
