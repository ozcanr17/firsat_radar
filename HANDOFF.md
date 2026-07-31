# Handoff

## Current stage

Stage 4: Analysis engine

Status: Complete

## Completed

- Added deterministic 0-100 demand, satisfaction, pain, momentum, and price-position metrics.
- Added category-relative percentile calculation with explicit small-sample risks.
- Added snapshot-based review-count growth and price-reduction momentum signals.
- Added rule-based Turkish delivery, quality, price, usability, safety, and general review labels.
- Added positive, neutral, and negative polarity plus low, medium, and high severity.
- Retained only redacted review evidence spans already present in the local database.
- Added metric coverage and evidence-quality confidence without filling unavailable metrics.
- Added confidence-adjusted opportunity scoring and five transparent opportunity patterns.
- Added structured metric evidence, risk codes, and validation-required hypotheses.
- Added idempotent analysis, opportunity, and review-label persistence.
- Added migration `20260731_0004` for analysis uniqueness constraints.
- Added the bounded `analyze` CLI command.
- Added `GET /api/v1/opportunities`.
- Added an operational opportunity ranking to the existing dashboard.

## Live verification

- Products analyzed: 3
- Analyses created: 3
- Opportunities created: 3
- Review labels created: 20
- Repeated run analyses created: 0
- Repeated run analyses reused: 3
- Repeated run labels created: 0
- Highest live score: 65.1
- Highest live pattern: `validated_pain`
- Highest result coverage: 100 percent
- Highest result confidence: 100 percent
- Review-label polarity counts: 11 positive, 3 neutral, 6 negative
- Model version: `rules-tr-v1`
- Final migration: `20260731_0004`

All runtime analysis uses persisted live data under the ignored `data/` directory. No analyzed market data is committed.

## Metric contract

- Demand: category percentile of the latest public evaluation count.
- Satisfaction: latest public rating normalized to 0-100.
- Pain: share of stored public reviews with at least one negative rule signal.
- Momentum: weighted non-negative review-count growth and price reduction between snapshots.
- Price position: inverse category price percentile.
- Coverage: share of the five metrics that are available.
- Confidence: coverage multiplied by listing, detail, and stored-review evidence quality.
- Opportunity score: available weighted metrics adjusted toward neutral when confidence is low.

## Verification

- Ruff lint: passed
- Ruff format check: passed
- Mypy strict mode: passed
- Pytest: 24 passed
- Clean migration chain: passed
- Live `analyze` first run: passed
- Live `analyze` repeated run: idempotent
- Live `/api/v1/opportunities`: HTTP 200 with evidence and risks
- Live dashboard: HTTP 200 with opportunity ranking

## Current commands

```bash
.venv/bin/python -m app.cli policy-check --source hepsiburada
.venv/bin/python -m app.cli crawl --source hepsiburada --limit-products 5 --limit-details 2
.venv/bin/python -m app.cli analyze --limit-products 60
.venv/bin/python -m app.cli serve
```

## Known limits

- The live category sample currently contains only three products, so percentile results carry a small-market risk.
- Turkish review labels are deterministic lexical rules and do not resolve sarcasm or complex context.
- Review-level star ratings remain unavailable in the observed visible DOM.
- Momentum requires two product snapshots and does not extrapolate missing history.
- The current dashboard is operational, not the final product interface.
- Scheduling remains inactive.

## Next stage

Stage 5 is ready: design and implement the full web interface for dashboard overview, products, product detail, opportunity evidence, run history, settings, JSON API navigation, and CSV export.
