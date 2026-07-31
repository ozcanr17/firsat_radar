import pytest
from sqlalchemy import select

from app.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import CategoryCursor
from app.db.session import build_engine, build_session_factory
from app.domain.crawl import CrawlLimits, CrawlSummary, RunStatus
from app.services.catalog import MAIN_CATEGORIES, CatalogMonitor, category_page_url


class FakeTargetCrawler:
    def __init__(self, summaries: list[CrawlSummary]) -> None:
        self.summaries = summaries
        self.targets: list[tuple[str, str, CrawlLimits]] = []

    async def crawl_target(
        self,
        target_url: str,
        category_name: str,
        limits: CrawlLimits,
    ) -> CrawlSummary:
        self.targets.append((target_url, category_name, limits))
        return self.summaries.pop(0)


def summary(
    run_id: int,
    products_seen: int = 60,
    signature: str = "a" * 64,
) -> CrawlSummary:
    return CrawlSummary(
        run_id=run_id,
        status=RunStatus.COMPLETED,
        products_seen=products_seen,
        products_created=products_seen,
        products_updated=0,
        snapshots_created=products_seen,
        details_created=0,
        reviews_created=0,
        fetches_created=2,
        error_code=None,
        listing_signature=signature,
    )


def test_category_page_url_preserves_query() -> None:
    url = "https://www.hepsiburada.com/telefonlar-c-1?filtre=aktif"

    assert category_page_url(url, 1) == url
    assert category_page_url(url, 3).endswith("filtre=aktif&sayfa=3")


@pytest.mark.asyncio
async def test_catalog_seeds_and_rotates_categories(settings: Settings) -> None:
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    crawler = FakeTargetCrawler([summary(1), summary(2)])
    monitor = CatalogMonitor(session_factory, crawler, 60)
    try:
        assert monitor.seed() == len(MAIN_CATEGORIES)
        assert monitor.seed() == 0

        result = await monitor.run_batch(2)
        status = monitor.status()

        assert result.products_seen == 120
        assert len(crawler.targets) == 2
        assert crawler.targets[0][1] != crawler.targets[1][1]
        assert status.category_count == len(MAIN_CATEGORIES)
        assert status.pages_scanned == 2
        assert status.pending_count == len(MAIN_CATEGORIES)
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_catalog_completes_short_category_page(settings: Settings) -> None:
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    crawler = FakeTargetCrawler(
        [
            summary(1, products_seen=36, signature="a" * 64),
            summary(2, products_seen=12, signature="b" * 64),
        ]
    )
    monitor = CatalogMonitor(session_factory, crawler, 60)
    try:
        monitor.seed()
        await monitor.run_next()
        for category in MAIN_CATEGORIES[1:]:
            with session_factory.begin() as session:
                cursor = session.scalar(
                    select(CategoryCursor).where(CategoryCursor.name == category.name)
                )
                assert cursor is not None
                cursor.enabled = False
        await monitor.run_next()

        with session_factory() as session:
            category = session.scalar(select(CategoryCursor).order_by(CategoryCursor.id))

        assert category is not None
        assert category.next_page == 1
        assert category.page_size == 36
        assert category.pages_scanned == 2
        assert category.sweeps_completed == 1
        assert category.last_completed_at is not None
        assert category.last_crawled_at is not None
    finally:
        engine.dispose()
