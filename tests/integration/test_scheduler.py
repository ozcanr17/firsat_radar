from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine

from app.config import Settings
from app.db.migrations import upgrade_database
from app.db.session import build_engine, build_session_factory
from app.domain.analysis import AnalysisSummary
from app.domain.crawl import CrawlLimits, CrawlSummary, RunStatus
from app.scheduler import RunLock, ScheduledPipeline, build_scheduler
from app.services.backup import BackupResult
from app.services.raw_store import PruneResult
from app.services.runtime_state import RuntimeStateService


class FakeCrawler:
    def __init__(self, outcomes: list[CrawlSummary | Exception]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def crawl(self, limits: CrawlLimits) -> CrawlSummary:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeCatalog:
    def __init__(self, outcome: CrawlSummary) -> None:
        self.outcome = outcome
        self.page_counts: list[int] = []

    async def run_batch(self, page_count: int) -> CrawlSummary:
        self.page_counts.append(page_count)
        return self.outcome


class FakeAnalyzer:
    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, limit: int = 200) -> AnalysisSummary:
        self.calls += 1
        return AnalysisSummary(
            products_seen=1,
            analyses_created=1,
            analyses_reused=0,
            opportunities_created=1,
            labels_created=0,
            labels_updated=0,
            model_version="test-v1",
        )


class FakeBackup:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.calls = 0

    def create(self, now: datetime | None = None) -> BackupResult:
        self.calls += 1
        self.path.write_bytes(b"backup")
        return BackupResult(
            path=self.path,
            size_bytes=6,
            integrity="ok",
            backups_removed=0,
        )


class FakeRetention:
    def __init__(self) -> None:
        self.calls = 0

    def prune(
        self,
        retention_days: int,
        now: datetime | None = None,
        dry_run: bool = True,
    ) -> PruneResult:
        self.calls += 1
        return PruneResult(scanned=3, eligible=2, deleted=2, bytes_deleted=100)


def crawl_summary(status: RunStatus, error_code: str | None = None) -> CrawlSummary:
    return CrawlSummary(
        run_id=1,
        status=status,
        products_seen=1,
        products_created=0,
        products_updated=1,
        snapshots_created=1,
        details_created=1,
        reviews_created=1,
        fetches_created=4,
        error_code=error_code,
        listing_signature="a" * 64,
    )


def build_pipeline(
    settings: Settings,
    crawler: FakeCrawler,
    catalog: FakeCatalog | None = None,
) -> tuple[
    ScheduledPipeline,
    RuntimeStateService,
    FakeAnalyzer,
    FakeBackup,
    FakeRetention,
    list[float],
    Engine,
]:
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    runtime = RuntimeStateService(session_factory)
    analyzer = FakeAnalyzer()
    backup = FakeBackup(settings.data_dir / "backups" / "test.db")
    retention = FakeRetention()
    waits: list[float] = []

    async def sleeper(delay: float) -> None:
        waits.append(delay)

    pipeline = ScheduledPipeline(
        settings,
        crawler,
        analyzer,
        backup,
        retention,
        runtime,
        catalog=catalog,
        sleeper=sleeper,
        now_provider=lambda: datetime(2026, 7, 31, tzinfo=UTC),
    )
    return pipeline, runtime, analyzer, backup, retention, waits, engine


@pytest.mark.asyncio
async def test_pipeline_retries_transient_exception_then_completes(settings: Settings) -> None:
    settings = Settings(
        environment="test",
        data_dir=settings.data_dir,
        retry_attempts=2,
        retry_delay_seconds=5,
    )
    crawler = FakeCrawler([RuntimeError("temporary"), crawl_summary(RunStatus.COMPLETED)])
    pipeline, runtime, analyzer, backup, retention, waits, engine = build_pipeline(
        settings, crawler
    )

    result = await pipeline.run()
    state = runtime.get()

    assert result.status == "completed"
    assert result.attempts == 2
    assert result.raw_files_deleted == 2
    assert crawler.calls == 2
    assert analyzer.calls == 1
    assert backup.calls == 1
    assert retention.calls == 1
    assert waits == [5.0]
    assert state.scheduler_status == "completed"
    assert state.consecutive_failures == 0
    assert state.last_backup_at is not None
    assert state.last_retention_at is not None
    engine.dispose()


@pytest.mark.asyncio
async def test_pipeline_uses_bounded_catalog_batch(settings: Settings) -> None:
    settings = Settings(
        environment="test",
        data_dir=settings.data_dir,
        catalog_enabled=True,
    )
    crawler = FakeCrawler([crawl_summary(RunStatus.FAILED)])
    catalog = FakeCatalog(crawl_summary(RunStatus.COMPLETED))
    pipeline, _, analyzer, _, _, _, engine = build_pipeline(settings, crawler, catalog)

    result = await pipeline.run()

    assert result.status == "completed"
    assert catalog.page_counts == [settings.catalog_pages_per_run]
    assert crawler.calls == 0
    assert analyzer.calls == 1
    engine.dispose()


@pytest.mark.asyncio
async def test_security_block_opens_circuit_and_prevents_next_run(settings: Settings) -> None:
    crawler = FakeCrawler([crawl_summary(RunStatus.BLOCKED, "listing_security_block")])
    pipeline, runtime, analyzer, backup, retention, _, engine = build_pipeline(settings, crawler)

    first = await pipeline.run()
    second = await pipeline.run()
    state = runtime.get()

    assert first.status == "circuit_open"
    assert second.status == "circuit_open"
    assert second.attempts == 0
    assert crawler.calls == 1
    assert analyzer.calls == 0
    assert backup.calls == 1
    assert retention.calls == 0
    assert state.circuit_is_open(datetime(2026, 7, 31, tzinfo=UTC)) is True
    reset = runtime.reset_circuit()
    assert reset.scheduler_status == "idle"
    assert reset.circuit_is_open(datetime(2026, 7, 31, tzinfo=UTC)) is False
    engine.dispose()


@pytest.mark.asyncio
async def test_cross_process_lock_skips_overlapping_job(settings: Settings) -> None:
    crawler = FakeCrawler([crawl_summary(RunStatus.COMPLETED)])
    pipeline, runtime, _, _, _, _, engine = build_pipeline(settings, crawler)

    with RunLock(pipeline.lock_path) as lock:
        assert lock.acquired is True
        result = await pipeline.run()

    assert result.status == "skipped_overlap"
    assert crawler.calls == 0
    assert runtime.get().scheduler_status == "skipped_overlap"
    engine.dispose()


def test_scheduler_has_single_instance_and_coalescing(settings: Settings) -> None:
    crawler = FakeCrawler([crawl_summary(RunStatus.COMPLETED)])
    pipeline, _, _, _, _, _, engine = build_pipeline(settings, crawler)
    scheduler = build_scheduler(settings, pipeline)
    job = scheduler.get_job("firsat-radar-crawl")

    assert job is not None
    assert job.max_instances == 1
    assert job.coalesce is True
    engine.dispose()
