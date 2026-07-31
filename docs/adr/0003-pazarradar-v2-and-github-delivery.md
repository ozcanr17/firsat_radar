# ADR 0003: PazarRadar v2 scope and GitHub delivery

## Status

Accepted on 2026-07-31.

## Context

The PazarRadar v2 document narrows the research scope to Hepsiburada Anne & Bebek, initially focusing on baby strollers, high chairs, and bottle/pacifier products. It requires sitemap-first discovery, no query-parameter pagination, no `/product-comment/` access, no personal reviewer data, one connection, a hard request ceiling, and evidence-backed commercial briefs.

The cached robots document advertises product and category sitemap indexes and disallows `/product/` and `/product-comment/`. A direct 2026-07-31 sitemap acceptance attempt returned the Hepsiburada security page. Collection stopped immediately. Sitemap discovery cannot be marked accepted until a later policy-gated attempt returns valid XML.

GitHub Pages can serve static files but cannot run FastAPI or SQLite. GitHub Actions can execute workflows, but hosted-runner access to Hepsiburada may be blocked and must never trigger bypass behavior.

## Decision

- Public delivery is a static, searchable Anne & Bebek analysis export on GitHub Pages.
- The local FastAPI application remains the full operational interface.
- Query-parameter catalog scheduling is disabled by default.
- GitHub-hosted execution is manual-only until sitemap XML access is accepted.
- The manual workflow checks policy, analyzes cached permitted data, and publishes without product-page collection.
- A security page, robots denial, HTTP 403, HTTP 429, CAPTCHA, or parser drift stops collection.
- Daily external requests are capped at 800 in code; the existing 6-12 second sequential limiter remains stricter than the document's four-second ceiling.
- GitHub Actions caches the SQLite database and policy state but never publishes raw evidence or reviewer text.
- The Pages artifact contains product facts, aggregate signals, recommendation evidence, risks, and validation steps only.

## Consequences

- The public site can be opened without a local process.
- The hosted bot is runnable but not scheduled automatically while sitemap access is unverified.
- GitHub Actions schedules can be delayed and public-repository schedules are disabled after 60 days without repository activity.
- Automatic sitemap discovery and the three-subcategory brief remain the next implementation milestone.
