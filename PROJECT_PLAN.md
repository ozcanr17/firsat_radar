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

## Stage 9: Product freshness and detail queue

Status: Ready.

Prioritize stale and high-signal products for detail and public-review refresh without coupling expensive detail navigation to broad catalog discovery.
