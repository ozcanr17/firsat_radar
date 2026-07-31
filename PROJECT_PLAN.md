# Implementation Plan

## Stage 0: Data-access discovery

Status: Complete with `GO` for browser-rendered public pages.

Validate the live robots policy, listing access, available fields, canonical product access, and review coverage at the smallest safe request volume. Record the decision in an ADR.

## Stage 1: Skeleton and database

Status: Complete.

Create the Python project, configuration, migrations, CLI, health endpoint, and basic web shell.

## Stage 2: Live listing slice

Status: Complete.

Implement policy gate, live listing discovery, normalization, provenance, snapshots, and idempotent persistence.

## Stage 3: Product detail and reviews

Status: Complete.

Collect only permitted fields, with explicit coverage and reason codes for unavailable data.

## Stage 4: Analysis engine

Status: Complete.

Implement deltas, percentiles, rule-based Turkish review labels, opportunity scores, evidence, and confidence.

## Stage 5: Web interface

Status: Complete.

Build the dashboard, products, product detail, opportunities, run history, settings, JSON API, and CSV export.

## Stage 6: Scheduling and hardening

Status: Complete.

Add non-overlapping scheduling, retries, circuit breaker, retention, backups, and operational documentation.

## Stage 7: Acceptance and delivery

Status: Complete.

Run the opt-in live smoke test, full quality checks, UI verification, and final documentation.

## Stage 8: Continuous catalog monitoring

Status: Complete.

Add persistent category cursors, bounded round-robin page traversal, repeated-page detection, catalog progress reporting, scheduler integration, and operational commands.

## Stage 9: Search and commercial decision support

Status: Complete.

Add product/category search, category and route filters, evidence-gated commercial recommendations, bounded detail/review collection, and starvation-free analysis prioritization.

## Stage 10: PazarRadar v2 and GitHub delivery

Status: Complete.

Adopt the Anne & Bebek scope, disable legacy query-pagination scheduling, add a public static research panel, and provide CI, Pages, and guarded manual bot workflows.

## Stage 11: Operator trade desk and watchlist refresh

Status: Complete.

Add prioritized product/category watch targets, direct due-product refresh, review pain clusters, persisted unit economics, GO/NO-GO decisions, and a public browser-side profitability calculator.

## Stage 12: Sitemap discovery and category briefs

Status: Blocked by source acceptance.

Validate an advertised sitemap as XML without bypass behavior, discover only the three initial Anne & Bebek subcategories, and generate category-level commercial briefs from permitted product-page evidence.
