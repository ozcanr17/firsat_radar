from dataclasses import dataclass
from datetime import UTC, datetime

from app.db.models import WatchTarget
from app.db.session import SessionFactory
from app.domain.crawl import CrawlSummary, RunStatus
from app.services.commerce import list_watch_targets
from app.services.crawl import CrawlService


@dataclass(frozen=True)
class WatchlistRefreshItem:
    target_id: int
    product_id: int
    label: str
    status: str
    error_code: str | None


@dataclass(frozen=True)
class WatchlistRefreshSummary:
    queued: int
    refreshed: int
    stopped: bool
    items: tuple[WatchlistRefreshItem, ...]


class WatchlistMonitor:
    def __init__(
        self,
        session_factory: SessionFactory,
        crawler: CrawlService,
    ) -> None:
        self.session_factory = session_factory
        self.crawler = crawler

    async def refresh_due(self, limit: int = 3) -> WatchlistRefreshSummary:
        if not 1 <= limit <= 10:
            raise ValueError("invalid_watchlist_limit")
        due = [
            target
            for target in list_watch_targets(self.session_factory)
            if target.enabled and target.refresh_due and target.product_id is not None
        ][:limit]
        items = []
        stopped = False
        for target in due:
            if target.product_id is None:
                continue
            summary = await self.crawler.refresh_product(target.product_id)
            self._mark_target(target.id, summary.status.value, datetime.now(UTC))
            items.append(
                WatchlistRefreshItem(
                    target_id=target.id,
                    product_id=target.product_id,
                    label=target.label,
                    status=summary.status.value,
                    error_code=summary.error_code,
                )
            )
            if summary.status not in {RunStatus.COMPLETED, RunStatus.UNCHANGED}:
                stopped = True
                break
        return WatchlistRefreshSummary(
            queued=len(due),
            refreshed=sum(
                item.status in {RunStatus.COMPLETED.value, RunStatus.UNCHANGED.value}
                for item in items
            ),
            stopped=stopped,
            items=tuple(items),
        )

    async def run_batch(self, page_count: int) -> CrawlSummary:
        result = await self.refresh_due(page_count)
        last_item = result.items[-1] if result.items else None
        status = RunStatus(last_item.status) if last_item else RunStatus.UNCHANGED
        if result.refreshed and not result.stopped:
            status = RunStatus.COMPLETED
        return CrawlSummary(
            run_id=last_item.target_id if last_item else 0,
            status=status,
            products_seen=len(result.items),
            products_created=0,
            products_updated=result.refreshed,
            snapshots_created=0,
            details_created=result.refreshed,
            reviews_created=0,
            fetches_created=0,
            error_code=last_item.error_code if result.stopped and last_item else None,
            listing_signature=None,
        )

    def _mark_target(self, target_id: int, status: str, checked_at: datetime) -> None:
        with self.session_factory.begin() as session:
            target = session.get_one(WatchTarget, target_id)
            target.last_status = status
            target.last_checked_at = checked_at
