# ADR 0002: Browser-rendered public data access

- Status: Accepted
- Decision: GO
- Checked at: 2026-07-31
- Supersedes: ADR 0001

## Context

Direct HTTP access returned a security block during the initial discovery. The project still requires real product, rating, review, and comparison data without a private API, credentials, or access-control bypass.

## Verified path

A normal rendered browser successfully completed this public navigation path:

1. Opened `https://www.hepsiburada.com/`.
2. Used the visible site search for `bebek arabası`.
3. Loaded `https://www.hepsiburada.com/ara?q=bebek+arabası`.
4. Read product cards from the rendered product region.
5. Opened a canonical product page linked by a visible product card.
6. Opened the public `-yorumlari` page linked by the product page.

## Observed data

The rendered listing exposed:

- Product title
- Product URL and external code
- Current price
- Rating
- Evaluation count
- Listing position
- Delivery and promotion labels when present

The rendered product page exposed:

- Canonical title and brand
- Rating and evaluation count
- Current price
- Seller
- Product description
- Product properties
- Origin and overseas-sale indicators when present
- Link to the public review page

The rendered review page exposed:

- Aggregate rating
- Total evaluation count
- Rating distribution
- Visible review text
- Review date
- Seller attribution
- Pagination controls

Reviewer names or initials are not required and will not be stored.

## Decision

Use a headed browser adapter as the primary Hepsiburada source implementation.

The adapter will read only the rendered DOM of public pages reached through visible site navigation. It will not call or inspect hidden APIs, intercept application network traffic, extract cookies, reuse private session data, or request `/api/` or `/product-comment/`.

## Operating constraints

- One browser tab and one navigation at a time.
- Random 6-12 second delay between product-page navigations.
- Initial run limited to 20 listing products, 5 product details, and 2 visible review pages per product.
- No automatic login.
- Immediate stop on HTTP 403, CAPTCHA, security interstitial, or access denial.
- No CAPTCHA solving, proxy rotation, fingerprint spoofing, or retry after a block in the same run.
- Only rendered, publicly visible text is parsed.
- Reviewer identity, profile link, avatar, and location are discarded.
- Every record stores its source URL, observation time, parser version, coverage, and confidence.
- No demo or fabricated market data.

## Architecture consequence

Playwright is required for the Hepsiburada adapter because the browser-rendered public path succeeds while direct HTTP access does not. HTTPX remains available for policy files and sources that permit direct requests.

The collection pipeline becomes:

`policy check -> headed browser -> visible listing DOM -> visible product DOM -> public review DOM -> normalize -> persist -> analyze`

## Scope

The decision is `GO` for the local MVP. Publication, commercial operation, or higher-volume collection requires a separate review of the platform terms and applicable law.
