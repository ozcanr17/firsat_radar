# PazarRadar v2

This repository implements the supplied PazarRadar v2 document under the following operating contract.

## Scope

- Source: Hepsiburada only.
- Department: Anne & Bebek.
- Initial focus: baby strollers, high chairs, and bottle/pacifier products.
- Discovery: sitemap-first after policy and XML acceptance.
- Evidence: permitted product pages and reviews visibly present on those pages.
- Output: explainable product signals and validation-required commercial briefs.

## Collection contract

- One sequential browser connection.
- Six to twelve seconds between requests.
- At most 800 external requests per UTC day.
- No query-parameter pagination.
- No `/product-comment/`, hidden API, proxy rotation, CAPTCHA bypass, or access-control bypass.
- Stop on policy denial, HTTP 403, HTTP 429, CAPTCHA, security page, or parser drift.
- Do not retain reviewer identity or direct contact information.

## Delivery contract

- GitHub Pages publishes a read-only, searchable snapshot without raw review evidence.
- The full FastAPI panel and SQLite database remain local.
- GitHub Actions collection is manual and policy-first until sitemap access is accepted.
- Public recommendations are research priorities, never guarantees of demand, profit, or production feasibility.

## Operating loop

1. Add known products or category hypotheses to the local Esnaf Masası.
2. The scheduler refreshes up to three due, resolved product targets per run.
3. Only reviews already visible on the product page are minimized and classified.
4. Review pain clusters, market signals, and data freshness determine research priority.
5. The operator enters real purchase and operating costs.
6. A product becomes actionable only after market evidence and unit economics agree.

Implementation rationale and source-access status are recorded in [ADR 0003](docs/adr/0003-pazarradar-v2-and-github-delivery.md).
