import asyncio
import fcntl
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self, TextIO
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import Settings
from app.domain.analysis import AnalysisSummary
from app.domain.crawl import CrawlLimits, CrawlSummary, RunStatus
from app.services.backup import BackupResult
from app.services.raw_store import PruneResult
from app.services.runtime_state import RuntimeStateService

SUCCESS_STATUSES = {RunStatus.COMPLETED, RunStatus.UNCHANGED}
IMMEDIATE_CIRCUIT_STATUSES = {
    RunStatus.BLOCKED,
    RunStatus.POLICY_DENIED,
    RunStatus.PARSER_DRIFT,
}


class CrawlOperation(Protocol):
    async def crawl(self, limits: CrawlLimits) -> CrawlSummary: ...


class CatalogOperation(Protocol):
    async def run_batch(self, page_count: int) -> CrawlSummary: ...


class AnalysisOperation(Protocol):
    def analyze(self, limit: int = 200) -> AnalysisSummary: ...


class BackupOperation(Protocol):
    def create(self, now: datetime | None = None) -> BackupResult: ...


class RetentionOperation(Protocol):
    def prune(
        self,
        retention_days: int,
        now: datetime | None = None,
        dry_run: bool = True,
    ) -> PruneResult: ...


@dataclass(frozen=True)
class ScheduledRunSummary:
    status: str
    crawl_status: str | None
    attempts: int
    analyses_created: int
    raw_files_deleted: int
    backup_path: str | None
    error_code: str | None


class RunLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: TextIO | None = None
        self.acquired = False

    def __enter__(self) -> Self:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return self
        self.handle = handle
        self.acquired = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.handle is None:
            return
        handle = self.handle
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class ScheduledPipeline:
    def __init__(
        self,
        settings: Settings,
        crawler: CrawlOperation,
        analyzer: AnalysisOperation,
        backup: BackupOperation,
        retention: RetentionOperation,
        runtime_state: RuntimeStateService,
        catalog: CatalogOperation | None = None,
        watchlist: CatalogOperation | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now_provider: Callable[[], datetime] | None = None,
        source_isolated: bool = False,
    ) -> None:
        self.settings = settings
        self.crawler = crawler
        self.analyzer = analyzer
        self.backup = backup
        self.retention = retention
        self.runtime_state = runtime_state
        self.catalog = catalog
        self.watchlist = watchlist
        self.sleeper = sleeper
        self.now_provider = now_provider or (lambda: datetime.now(UTC))
        self.source_isolated = source_isolated
        self.lock_path = settings.data_dir / "runtime" / "scheduled-crawl.lock"

    async def run(self) -> ScheduledRunSummary:
        with RunLock(self.lock_path) as lock:
            if not lock.acquired:
                self.runtime_state.mark_skipped("skipped_overlap", "job_overlap")
                return ScheduledRunSummary(
                    status="skipped_overlap",
                    crawl_status=None,
                    attempts=0,
                    analyses_created=0,
                    raw_files_deleted=0,
                    backup_path=None,
                    error_code="job_overlap",
                )
            current = self.runtime_state.get()
            if current.circuit_is_open(self.now_provider()):
                self.runtime_state.mark_skipped("circuit_open", current.last_error_code)
                return ScheduledRunSummary(
                    status="circuit_open",
                    crawl_status=None,
                    attempts=0,
                    analyses_created=0,
                    raw_files_deleted=0,
                    backup_path=None,
                    error_code=current.last_error_code,
                )
            started_at = self.now_provider()
            self.runtime_state.mark_running(started_at)
            try:
                backup_result = self.backup.create(started_at)
                self.runtime_state.mark_backup(started_at)
            except Exception as error:
                error_code = type(error).__name__.casefold()
                self.runtime_state.mark_failure(
                    self.now_provider(),
                    error_code,
                    self.settings.circuit_failure_threshold,
                    self.settings.circuit_cooldown_hours,
                )
                return ScheduledRunSummary(
                    status="failed",
                    crawl_status=None,
                    attempts=0,
                    analyses_created=0,
                    raw_files_deleted=0,
                    backup_path=None,
                    error_code=error_code,
                )
            try:
                crawl_summary, attempts = await self._crawl_with_retry()
            except Exception as error:
                error_code = type(error).__name__.casefold()
                self.runtime_state.mark_failure(
                    self.now_provider(),
                    error_code,
                    self.settings.circuit_failure_threshold,
                    self.settings.circuit_cooldown_hours,
                )
                return ScheduledRunSummary(
                    status="failed",
                    crawl_status=None,
                    attempts=self.settings.retry_attempts,
                    analyses_created=0,
                    raw_files_deleted=0,
                    backup_path=str(backup_result.path),
                    error_code=error_code,
                )
            if crawl_summary.status not in SUCCESS_STATUSES and self.source_isolated:
                error_code = crawl_summary.error_code or crawl_summary.status.value
                retention_at = self.now_provider()
                self.retention.prune(
                    self.settings.raw_retention_days,
                    now=retention_at,
                    dry_run=False,
                )
                self.runtime_state.mark_degraded(
                    self.now_provider(),
                    error_code,
                    backup_at=started_at,
                    retention_at=retention_at,
                )
                return ScheduledRunSummary(
                    status="sources_degraded",
                    crawl_status=crawl_summary.status.value,
                    attempts=attempts,
                    analyses_created=0,
                    raw_files_deleted=0,
                    backup_path=str(backup_result.path),
                    error_code=error_code,
                )
            if crawl_summary.status not in SUCCESS_STATUSES:
                force_open = crawl_summary.status in IMMEDIATE_CIRCUIT_STATUSES
                error_code = crawl_summary.error_code or crawl_summary.status.value
                state = self.runtime_state.mark_failure(
                    self.now_provider(),
                    error_code,
                    self.settings.circuit_failure_threshold,
                    self.settings.circuit_cooldown_hours,
                    force_open=force_open,
                )
                return ScheduledRunSummary(
                    status=state.scheduler_status,
                    crawl_status=crawl_summary.status.value,
                    attempts=attempts,
                    analyses_created=0,
                    raw_files_deleted=0,
                    backup_path=str(backup_result.path),
                    error_code=error_code,
                )
            try:
                analysis_summary = self.analyzer.analyze(self.settings.scheduler_products)
                retention_at = self.now_provider()
                prune_result = self.retention.prune(
                    self.settings.raw_retention_days,
                    now=retention_at,
                    dry_run=False,
                )
                self.runtime_state.mark_retention(retention_at)
            except Exception as error:
                error_code = type(error).__name__.casefold()
                self.runtime_state.mark_failure(
                    self.now_provider(),
                    error_code,
                    self.settings.circuit_failure_threshold,
                    self.settings.circuit_cooldown_hours,
                )
                return ScheduledRunSummary(
                    status="failed",
                    crawl_status=crawl_summary.status.value,
                    attempts=attempts,
                    analyses_created=0,
                    raw_files_deleted=0,
                    backup_path=str(backup_result.path),
                    error_code=error_code,
                )
            self.runtime_state.mark_success(
                self.now_provider(),
                backup_at=started_at,
                retention_at=retention_at,
            )
            return ScheduledRunSummary(
                status="completed",
                crawl_status=crawl_summary.status.value,
                attempts=attempts,
                analyses_created=analysis_summary.analyses_created,
                raw_files_deleted=prune_result.deleted,
                backup_path=str(backup_result.path),
                error_code=None,
            )

    async def _crawl_with_retry(self) -> tuple[CrawlSummary, int]:
        limits = CrawlLimits(
            products=min(
                self.settings.scheduler_products,
                self.settings.crawl_max_products,
                60,
            ),
            details=self.settings.scheduler_details,
        )
        for attempt in range(1, self.settings.retry_attempts + 1):
            try:
                summaries: list[CrawlSummary] = []
                if self.settings.watchlist_enabled and self.watchlist is not None:
                    summaries.append(
                        await self.watchlist.run_batch(self.settings.watchlist_targets_per_run)
                    )
                    if summaries[-1].status not in SUCCESS_STATUSES:
                        return summaries[-1], attempt
                if self.settings.catalog_enabled and self.catalog is not None:
                    summaries.append(
                        await self.catalog.run_batch(self.settings.catalog_pages_per_run)
                    )
                if not summaries or all(summary.run_id == 0 for summary in summaries):
                    summaries.append(await self.crawler.crawl(limits))
                return merge_crawl_summaries(summaries), attempt
            except Exception:
                if attempt >= self.settings.retry_attempts:
                    raise
                delay = self.settings.retry_delay_seconds * 2 ** (attempt - 1)
                await self.sleeper(delay)
        raise RuntimeError("Retry loop exhausted")


def build_scheduler(settings: Settings, pipeline: ScheduledPipeline) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))
    scheduler.add_job(
        pipeline.run,
        trigger=IntervalTrigger(
            hours=settings.scheduler_interval_hours,
            timezone=ZoneInfo(settings.timezone),
        ),
        id="firsat-radar-crawl",
        name="Firsat Radar crawl and analysis",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
        replace_existing=True,
        next_run_time=datetime.now(ZoneInfo(settings.timezone)),
    )
    return scheduler


def merge_crawl_summaries(summaries: list[CrawlSummary]) -> CrawlSummary:
    if not summaries:
        raise ValueError("empty_crawl_summaries")
    failure = next(
        (summary for summary in summaries if summary.status not in SUCCESS_STATUSES),
        None,
    )
    last = failure or summaries[-1]
    status = (
        last.status
        if failure is not None
        else (
            RunStatus.COMPLETED
            if any(summary.status is RunStatus.COMPLETED for summary in summaries)
            else RunStatus.UNCHANGED
        )
    )
    return CrawlSummary(
        run_id=last.run_id,
        status=status,
        products_seen=sum(summary.products_seen for summary in summaries),
        products_created=sum(summary.products_created for summary in summaries),
        products_updated=sum(summary.products_updated for summary in summaries),
        snapshots_created=sum(summary.snapshots_created for summary in summaries),
        details_created=sum(summary.details_created for summary in summaries),
        reviews_created=sum(summary.reviews_created for summary in summaries),
        fetches_created=sum(summary.fetches_created for summary in summaries),
        error_code=failure.error_code if failure is not None else None,
        listing_signature=None,
    )


async def serve_scheduler(settings: Settings, pipeline: ScheduledPipeline) -> None:
    scheduler = build_scheduler(settings, pipeline)
    scheduler.start()
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    finally:
        scheduler.shutdown(wait=False)
