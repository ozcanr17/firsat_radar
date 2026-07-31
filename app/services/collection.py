from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.config import Settings
from app.domain.crawl import CrawlSummary, RunStatus
from app.scheduler import IMMEDIATE_CIRCUIT_STATUSES, SUCCESS_STATUSES, merge_crawl_summaries
from app.services.source_state import SourceStateService


class BatchOperation(Protocol):
    async def run_batch(self, page_count: int) -> CrawlSummary: ...


@dataclass(frozen=True)
class SourceCollection:
    source_name: str
    watchlist: BatchOperation | None = None
    catalog: BatchOperation | None = None


@dataclass(frozen=True)
class SourceOutcome:
    source_name: str
    status: str
    error_code: str | None


THROTTLE_SUFFIXES = ("_rate_limited", "_rate_limit_cooldown", "daily_quota_reached")


def is_throttle_code(error_code: str) -> bool:
    return error_code.endswith(THROTTLE_SUFFIXES)


def empty_summary(status: RunStatus = RunStatus.UNCHANGED) -> CrawlSummary:
    return CrawlSummary(
        run_id=0,
        status=status,
        products_seen=0,
        products_created=0,
        products_updated=0,
        snapshots_created=0,
        details_created=0,
        reviews_created=0,
        fetches_created=0,
        error_code=None,
        listing_signature=None,
    )


class MultiSourceCollector:
    def __init__(
        self,
        settings: Settings,
        source_state: SourceStateService,
        collections: tuple[SourceCollection, ...],
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.source_state = source_state
        self.collections = collections
        self.now_provider = now_provider or (lambda: datetime.now(UTC))
        self.last_outcomes: tuple[SourceOutcome, ...] = ()

    async def run_batch(self, page_count: int) -> CrawlSummary:
        summaries: list[CrawlSummary] = []
        failures: list[CrawlSummary] = []
        outcomes: list[SourceOutcome] = []
        for collection in self.collections:
            state = self.source_state.get(collection.source_name)
            if state.circuit_is_open(self.now_provider()):
                outcomes.append(
                    SourceOutcome(collection.source_name, "circuit_open", state.last_error_code)
                )
                continue
            self.source_state.mark_running(collection.source_name, self.now_provider())
            try:
                summary = await self._run_source(collection, page_count)
            except Exception as error:
                error_code = type(error).__name__.casefold()
                self._record_failure(collection.source_name, error_code, force_open=False)
                outcomes.append(SourceOutcome(collection.source_name, "failed", error_code))
                failures.append(empty_summary(RunStatus.FAILED))
                continue
            if summary.status in SUCCESS_STATUSES:
                self.source_state.mark_success(collection.source_name, self.now_provider())
                outcomes.append(SourceOutcome(collection.source_name, summary.status.value, None))
                summaries.append(summary)
                continue
            error_code = summary.error_code or summary.status.value
            self._record_failure(
                collection.source_name,
                error_code,
                force_open=summary.status in IMMEDIATE_CIRCUIT_STATUSES,
            )
            outcomes.append(SourceOutcome(collection.source_name, summary.status.value, error_code))
            failures.append(summary)
        self.last_outcomes = tuple(outcomes)
        if summaries:
            return merge_crawl_summaries(summaries)
        if failures:
            return failures[-1]
        return empty_summary()

    async def _run_source(self, collection: SourceCollection, page_count: int) -> CrawlSummary:
        parts: list[CrawlSummary] = []
        if self.settings.watchlist_enabled and collection.watchlist is not None:
            parts.append(
                await collection.watchlist.run_batch(self.settings.watchlist_targets_per_run)
            )
            if parts[-1].status not in SUCCESS_STATUSES:
                return parts[-1]
        if self.settings.catalog_enabled and collection.catalog is not None:
            parts.append(await collection.catalog.run_batch(page_count))
        if not parts:
            return empty_summary()
        return merge_crawl_summaries(parts)

    def _record_failure(self, source_name: str, error_code: str, force_open: bool) -> None:
        if is_throttle_code(error_code):
            self.source_state.mark_throttled(source_name, self.now_provider(), error_code)
            return
        self.source_state.mark_failure(
            source_name,
            self.now_provider(),
            error_code,
            self.settings.circuit_failure_threshold,
            self.settings.circuit_cooldown_hours,
            force_open=force_open,
        )
