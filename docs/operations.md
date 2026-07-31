# Operations

## Processes

Run the web panel and scheduler as separate local processes:

```bash
.venv/bin/python -m app.cli serve
.venv/bin/python -m app.cli schedule
```

The interval scheduler waits for the configured interval before its first job. Use an explicit one-time run when an immediate policy-gated collection is intended:

```bash
.venv/bin/python -m app.cli scheduled-run
```

## Catalog monitoring

The catalog queue contains 17 public top-level categories. Each category persists its next page, observed page size, last product signature, pages scanned, completed sweeps, and last status. The hourly scheduler processes three least-recently-crawled category pages by default. Each page enriches at most two products with public detail and first-page review evidence.

```bash
.venv/bin/python -m app.cli catalog-seed
.venv/bin/python -m app.cli catalog-status
.venv/bin/python -m app.cli catalog-run --pages 1
```

Reset only the catalog cursor progress after a verified pagination change:

```bash
.venv/bin/python -m app.cli catalog-reset --confirm
```

Resetting cursors does not delete products, snapshots, reviews, fetch provenance, or raw evidence.

## Non-overlap

The scheduler uses both APScheduler `max_instances=1` and an operating-system file lock at `data/runtime/scheduled-crawl.lock`. A second process records `skipped_overlap` and performs no crawl.

## Retry and circuit breaker

Only unexpected transient exceptions are retried. The default is two total attempts with bounded exponential delay. Returned access blocks, policy denials, parser drift, HTTP 403, HTTP 429, and CAPTCHA states are not retried.

Access blocks, policy denials, and parser drift open the circuit immediately. Other failures open it after the configured consecutive-failure threshold. While open, scheduled jobs perform no backup, navigation, crawl, analysis, or retention work.

Inspect state:

```bash
.venv/bin/python -m app.cli runtime-status
```

Reset the circuit only after the external access condition or parser issue has been investigated:

```bash
.venv/bin/python -m app.cli circuit-reset
```

## Backups

Every scheduled job creates an online SQLite backup before crawling and verifies it with `PRAGMA integrity_check`. Backups are stored under `data/backups`; only the configured newest count is retained.

Create a manual backup:

```bash
.venv/bin/python -m app.cli backup
```

Recovery procedure:

1. Stop the web and scheduler processes.
2. Create a copy of the current database file outside `data`.
3. Select a verified `data/backups/firsat-radar-*.db` file.
4. Copy it to the configured database path as `firsat_radar.db`.
5. Run `.venv/bin/python -m app.cli doctor`.
6. Start the web panel and inspect `/healthz`, `/runs`, and `/settings` before restarting the scheduler.

## Raw evidence retention

Raw compressed evidence is retained for seven days by default. Scheduled cleanup only targets `*.gz` files inside `data/raw`.

Preview cleanup without deletion:

```bash
.venv/bin/python -m app.cli prune-raw --dry-run
```

Apply cleanup:

```bash
.venv/bin/python -m app.cli prune-raw --apply
```

## Operational checks

```bash
.venv/bin/python -m app.cli doctor
.venv/bin/python -m app.cli runtime-status
curl http://127.0.0.1:8000/healthz
```

The Settings panel shows scheduler state, failure count, circuit expiry, last backup, and last retention time.

The web process and scheduler are independent. `open-panel` only starts the web process. Continuous monitoring requires the `schedule` command to remain running.
