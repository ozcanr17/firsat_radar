# Operations

## Processes

Run the web panel and scheduler as separate local processes:

```bash
.venv/bin/python -m app.cli serve
.venv/bin/python -m app.cli schedule
```

The interval scheduler starts one guarded cycle at service startup and repeats at the configured interval. Use an explicit one-time run when an additional immediate collection is intended:

```bash
.venv/bin/python -m app.cli scheduled-run
```

The same action is available from the Radar Center with **Şimdi tara**.

## Watchlist monitoring

The scheduler processes up to three due targets per run. Priority combines the operator's priority, data age, opportunity score, and unresolved discovery state. New Hepsiburada product URLs are discovered from their public product page and linked to the target. Category targets scan their configured public category page. Refreshes classify only reviews already visible on the opened product page.

```bash
.venv/bin/python -m app.cli watchlist-refresh --limit 3
```

Product and category targets are managed from the Radar Center or `/trade-desk`.

## Category discovery agents

The category monitor is enabled by default. It rotates across 17 bounded Hepsiburada category cursors, prioritizing high-volume categories such as computers, phones, home electronics, appliances, baby products, cosmetics, supermarket, and sports. Three pages are processed per hourly cycle by default. Each category agent can be enabled or disabled from the Radar Center.

```bash
.venv/bin/python -m app.cli catalog-status
```

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

Local development can run the web process and scheduler separately. In Railway, the embedded scheduler runs inside the single authenticated web service and the `/data` volume stores its state. Keep the service at one replica.

Collection remains bounded and policy-gated. Public page access is not treated as permission to bypass robots rules, authentication, CAPTCHA, HTTP 403/429 responses, or marketplace terms.
