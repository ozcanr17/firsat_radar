# Handoff

## Current stage

Stage 1: Skeleton and database

Status: Complete

## Completed

- Added a Python 3.12 package with pinned runtime and development dependencies.
- Generated a fully resolved `requirements.lock`.
- Added environment-based configuration and managed local data directories.
- Added the complete initial SQLite schema for sources, crawl runs, fetch provenance, products, snapshots, offers, reviews, labels, analyses, opportunities, and settings.
- Added Alembic migration `20260731_0001`.
- Added `init-db`, `doctor`, and `serve` CLI commands.
- Added `/healthz` with database readiness and latest-run state.
- Added a server-rendered dashboard shell with an explicit `NO_DATA` state.
- Added unit and integration tests.
- Preserved the no-demo-data rule.

## Verification

- Ruff lint: passed
- Ruff format check: passed
- Mypy strict mode: passed
- Pytest: 5 passed
- Initial migration: passed on a clean temporary SQLite database
- CLI doctor: `status=ok`, `migration_ready=true`
- Git worktree before commit: reviewed with no unrelated changes

## Current commands

```bash
.venv/bin/python -m app.cli init-db
.venv/bin/python -m app.cli doctor
.venv/bin/python -m app.cli serve
```

## Known limits

- The browser adapter is not implemented yet.
- No live product data has been persisted.
- The dashboard intentionally shows `NO_DATA`.
- Scheduling and analysis remain inactive.

## Next stage

Stage 2 is ready: implement the policy gate, headed browser listing discovery, normalization, provenance, idempotent product upsert, and product snapshots.
