# Handoff

## Current stage

Stage 6: Scheduling and hardening

Status: Complete

## Completed

- Added a separate APScheduler process with configurable 12-hour intervals.
- Added APScheduler `max_instances=1`, coalescing, and misfire protection.
- Added an operating-system file lock for non-overlap across scheduler processes.
- Added bounded exponential retry for unexpected transient exceptions only.
- Kept access blocks, policy denials, parser drift, HTTP 403, HTTP 429, and CAPTCHA states non-retryable.
- Added immediate circuit opening for access blocks, policy denials, and parser drift.
- Added threshold-based circuit opening for other consecutive failures.
- Added persistent scheduler, failure, circuit, backup, and retention state.
- Added online SQLite backup with `PRAGMA integrity_check` verification.
- Added bounded backup retention under `data/backups`.
- Added seven-day compressed raw-evidence retention restricted to `data/raw/*.gz`.
- Added dry-run by default for manual raw-evidence cleanup.
- Added migration `20260731_0005` for runtime state.
- Extended `/healthz` with scheduler and circuit state.
- Added scheduler state, failure count, circuit expiry, backup, and retention fields to the Settings panel.
- Added `backup`, `prune-raw`, `runtime-status`, `circuit-reset`, `scheduled-run`, and `schedule` CLI commands.
- Added operational and recovery documentation in `docs/operations.md`.

## Safety contract

- Browser navigation remains single-tab and sequential.
- Cross-process scheduled overlap performs zero crawl work.
- Open circuit performs zero backup, navigation, crawl, analysis, or retention work.
- Security blocks are never retried.
- Manual retention defaults to preview mode.
- Automated deletion only targets expired `*.gz` files inside the configured raw directory.
- A verified database backup is created before each scheduled crawl.
- Circuit reset is manual and documented for investigated recovery only.

## Local acceptance

- Runtime migration: `20260731_0005`
- Manual SQLite backup: created
- Backup size: 122880 bytes
- Backup integrity: `ok`
- Raw files scanned: 9
- Raw files eligible after seven days: 0
- Raw files deleted from live data: 0
- Scheduler state: `idle`
- Consecutive failures: 0
- Circuit open: no
- Live market requests during Stage 6 acceptance: 0

## Failure and recovery verification

- Unexpected transient exception retried once and succeeded on attempt two.
- Retry delay remained bounded and deterministic in tests.
- Security block opened the circuit immediately.
- A second job under open circuit performed zero crawl calls.
- Cross-process lock rejected an overlapping job.
- Successful job reset failure count and circuit state.
- Manual circuit reset cleared the persisted breaker state.
- Backup retention removed only backups beyond the configured newest count.
- Raw retention dry-run reported candidates without deletion.
- Raw retention apply removed only an expired test fixture.

## Verification

- Ruff lint: passed
- Ruff format check: passed
- Mypy strict mode: passed
- Pytest: 31 passed
- Pip dependency check: passed
- Clean migration chain: passed
- No Python code comments: passed

## Operational commands

```bash
.venv/bin/python -m app.cli backup
.venv/bin/python -m app.cli prune-raw --dry-run
.venv/bin/python -m app.cli runtime-status
.venv/bin/python -m app.cli scheduled-run
.venv/bin/python -m app.cli schedule
.venv/bin/python -m app.cli circuit-reset
```

## Known limits

- The scheduler is a separate foreground process and is not installed as a macOS launch agent.
- SQLite recovery is documented but intentionally not automated over the active database.
- Circuit reset remains a manual operator decision.
- Remote deployment, authentication, and alert delivery remain out of scope.

## Next stage

Stage 7 is ready: run final acceptance, verify installation from a clean environment, confirm all UI and operational paths, audit repository contents, and produce the final delivery handoff.
