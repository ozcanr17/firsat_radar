from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import Product, Source, WatchTarget
from app.db.session import SessionFactory
from app.domain.crawl import CrawlLimits, CrawlSummary, RunStatus
from app.services.commerce import list_watch_targets
from app.services.crawl import CrawlService


@dataclass(frozen=True)
class WatchlistRefreshItem:
    target_id: int
    product_id: int | None
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
        crawlers: dict[str, CrawlService] | None = None,
        source_names: frozenset[str] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.crawler = crawler
        self.crawlers = {crawler.source_name: crawler, **(crawlers or {})}
        self.source_names = source_names

    def _in_scope(self, source_name: str) -> bool:
        return self.source_names is None or source_name in self.source_names

    async def refresh_due(self, limit: int = 3) -> WatchlistRefreshSummary:
        if not 1 <= limit <= 10:
            raise ValueError("invalid_watchlist_limit")
        due = [
            target
            for target in list_watch_targets(self.session_factory)
            if target.enabled
            and target.refresh_due
            and target.source_url is not None
            and self._in_scope(target.source_name)
        ][:limit]
        items = []
        stopped = False
        for target in due:
            crawler = self.crawlers.get(target.source_name)
            if crawler is None:
                self._mark_target(target.id, RunStatus.FAILED.value, datetime.now(UTC))
                items.append(
                    WatchlistRefreshItem(
                        target_id=target.id,
                        product_id=target.product_id,
                        label=target.label,
                        status=RunStatus.FAILED.value,
                        error_code="connector_unavailable",
                    )
                )
                stopped = True
                break
            if target.product_id is not None:
                summary = await crawler.refresh_product(target.product_id)
            elif target.target_type == "product" and target.source_url is not None:
                summary = await crawler.discover_product(
                    target.source_url,
                    target.label,
                    target.category,
                )
                self._link_product(target.id, target.source_url, crawler)
            elif target.source_url is not None:
                summary = await crawler.crawl_target(
                    target.source_url,
                    target.category or target.label,
                    CrawlLimits(
                        products=crawler.settings.catalog_products_per_page,
                        details=crawler.settings.catalog_details_per_page,
                    ),
                )
            else:
                continue
            self._mark_target(target.id, summary.status.value, datetime.now(UTC))
            product_id = self._product_id(target.id)
            items.append(
                WatchlistRefreshItem(
                    target_id=target.id,
                    product_id=product_id,
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

    def _link_product(
        self,
        target_id: int,
        source_url: str,
        crawler: CrawlService,
    ) -> None:
        external_id = crawler.external_id_extractor(source_url)
        if external_id is None:
            return
        with self.session_factory.begin() as session:
            target = session.get_one(WatchTarget, target_id)
            source = session.scalar(select(Source).where(Source.name == crawler.source_name))
            if source is None:
                return
            product = session.scalar(
                select(Product).where(
                    Product.source_id == source.id,
                    Product.external_id == external_id,
                )
            )
            if product is not None:
                target.product_id = product.id

    def _product_id(self, target_id: int) -> int | None:
        with self.session_factory() as session:
            return session.get_one(WatchTarget, target_id).product_id
