# ADR 0001: Hepsiburada data access

- Status: Accepted
- Decision: STOP
- Checked at: 2026-07-31T13:24:34Z
- Source: Hepsiburada
- Intended category: Anne, Bebek, Oyuncak

## Context

The project plan requires a data-access discovery stage before application development. Legal and source-policy compliance takes precedence over feature delivery. A blocked response must open the circuit breaker, end the run, and must not be bypassed.

## Evidence

The current `robots.txt` was read from `https://www.hepsiburada.com/robots.txt`.

For the wildcard user-agent group, the policy explicitly disallows these relevant paths and patterns:

- `/api/`
- `/product-comment/`
- `/product/`
- filtered and sorted URL patterns

The policy publishes category, product, and review sitemaps, but sitemap publication is not treated as permission to request otherwise restricted paths.

The first direct, low-impact request from the current runtime targeted:

`https://www.hepsiburada.com/sitemaps/category/sitemap.xml`

Request constraints:

- User agent: `FirsatRadar/0.1 (local research)`
- Timeout: 20 seconds
- Concurrency: 1
- Retries: 0

Observed result:

- HTTP status: 403
- Response title: `Hepsiburada | Güvenlik`
- Response contained a Hepsiburada security block/CAPTCHA iframe

No category, product, hidden API, or comment request was attempted after the 403 response.

## Access matrix

| Surface | Robots decision | Runtime result | Usable now |
| --- | --- | --- | --- |
| `robots.txt` | Public policy file | Read successfully | Yes, policy only |
| Category sitemap | Listed in robots | HTTP 403 security block | No |
| Anne, Bebek, Oyuncak listing | Candidate path not confirmed | Not requested after circuit breaker opened | No |
| Canonical product page | Unknown until a listing is available | Not requested | No |
| Visible product reviews | `/product-comment/` is disallowed | Not requested | No |
| Hidden API | `/api/` is disallowed | Not requested | No |

## Decision

The decision is `STOP` for the current source and runtime.

The environment cannot establish a permitted, accessible listing-to-product path without violating the mandatory stop rule. The project will not substitute demo, seed, fixture, cached search-engine, or fabricated market data.

## Consequences

- Stage 1 application development is paused.
- No crawler, parser, database, analysis engine, or market-data UI is created.
- No retry, CAPTCHA handling, proxy rotation, browser fingerprinting, cookie acquisition, or hidden endpoint discovery will be attempted.
- A new ADR is required before implementation resumes.

## Required decision

Choose one path:

1. Provide documented Hepsiburada permission or official API access suitable for the intended data.
2. Approve a different public source whose robots policy, terms, and live access permit the MVP workflow.
