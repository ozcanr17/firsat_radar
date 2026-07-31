from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Self

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import (
    CrawlRun,
    Fetch,
    Product,
    ProductDetail,
    ProductSnapshot,
    Review,
    WatchTarget,
)
from app.db.session import build_engine, build_session_factory
from app.domain.crawl import (
    CategoryLink,
    CrawlLimits,
    FetchedDocument,
    ListingResult,
    PolicyDecision,
    PolicyState,
    ProductDetailResult,
    ProductStub,
    ReviewStub,
    RunStatus,
)
from app.main import create_app
from app.services.commerce import WatchTargetInput, add_watch_target
from app.services.crawl import CrawlService
from app.services.watchlist import WatchlistMonitor


class FakeAdapter:
    def __init__(
        self,
        listing: ListingResult,
        detail: ProductDetailResult | None = None,
    ) -> None:
        self.listing = listing
        self.detail = detail

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def policy_check(self, url: str) -> PolicyDecision:
        return PolicyDecision(
            state=PolicyState.ALLOWED,
            url=url,
            checked_at=datetime.now(UTC),
            status_code=200,
            content="User-agent: *\nDisallow: /api/",
            content_hash="policy-hash",
            cached=False,
        )

    async def discover(self, start_url: str, limits: CrawlLimits) -> ListingResult:
        return self.listing

    async def enrich(self, product: ProductStub) -> ProductDetailResult:
        if self.detail is None:
            raise RuntimeError("Detail fixture unavailable")
        return self.detail


def build_listing() -> ListingResult:
    observed_at = datetime.now(UTC)
    return ListingResult(
        url="https://www.hepsiburada.com/anne-bebek-oyuncak-c-2147483639",
        fetched_at=observed_at,
        status_code=200,
        content_hash="listing-hash",
        raw_html="<main><article>live</article></main>",
        products=(
            ProductStub(
                external_id="HBCV0000000001",
                source_url="https://www.hepsiburada.com/urun-p-HBCV0000000001",
                title="Canlı Ürün",
                price=Decimal("1249.90"),
                old_price=None,
                rating=4.6,
                review_count=328,
                rank=1,
                image_url="https://images.example/live.jpg",
                delivery_text="Yarın kargoda",
                coverage=1.0,
                confidence=1.0,
            ),
        ),
        candidate_count=1,
        coverage=1.0,
        parser_version="test-v1",
    )


def build_listing_with_categories() -> ListingResult:
    listing = build_listing()
    return ListingResult(
        **{
            **listing.__dict__,
            "category_links": (
                CategoryLink(
                    label="Bebek Arabaları",
                    url="https://www.hepsiburada.com/bebek-arabalari-c-600001",
                ),
                CategoryLink(
                    label="Bebek Gıdaları",
                    url="https://www.hepsiburada.com/bebek-gidalari-c-600002",
                ),
            ),
        }
    )


def build_category_only_listing() -> ListingResult:
    listing = build_listing_with_categories()
    return ListingResult(
        **{
            **listing.__dict__,
            "products": (),
            "candidate_count": 0,
        }
    )


def build_detail() -> ProductDetailResult:
    observed_at = datetime.now(UTC)
    canonical_url = "https://www.hepsiburada.com/canli-urun-p-HBCV0000000001"
    review_url = f"{canonical_url}-yorumlari"
    review = ReviewStub(
        source_review_id="a" * 64,
        rating=None,
        review_date=observed_at,
        text_redacted="Paketleme özenli ve ürün kullanışlı.",
        source_url=review_url,
    )
    return ProductDetailResult(
        listing_external_id="HBCV0000000001",
        canonical_url=canonical_url,
        title="Canlı Ürün Detayı",
        brand="Canlı Marka",
        seller="Canlı Satıcı",
        description="Görünür ürün açıklaması",
        attributes={"Menşei": "TR - Türkiye", "Stok Adedi": "10 adetten az"},
        origin="TR - Türkiye",
        overseas_sale="Yok",
        stock="10 adetten az",
        review_url=review_url,
        coverage=1.0,
        confidence=1.0,
        reason_codes=(),
        detail_document=FetchedDocument(
            url=canonical_url,
            fetched_at=observed_at,
            status_code=200,
            content_hash="detail-hash",
            raw_html="<main>visible detail</main>",
            parser_version="detail-test-v1",
            coverage=1.0,
            confidence=1.0,
        ),
        reviews=(review,),
        review_document=FetchedDocument(
            url=review_url,
            fetched_at=observed_at,
            status_code=200,
            content_hash="review-hash",
            raw_html="<main data-identity-redacted='true'>visible review</main>",
            parser_version="review-test-v1",
            coverage=1.0,
            confidence=1.0,
        ),
    )


@pytest.mark.asyncio
async def test_crawl_is_idempotent(settings: Settings) -> None:
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    listing = build_listing()
    service = CrawlService(settings, session_factory, lambda: FakeAdapter(listing))
    try:
        first = await service.crawl(CrawlLimits(products=20))
        second = await service.crawl(CrawlLimits(products=20))

        with session_factory() as session:
            product_count = session.scalar(select(func.count()).select_from(Product))
            snapshot_count = session.scalar(select(func.count()).select_from(ProductSnapshot))
            fetch_count = session.scalar(select(func.count()).select_from(Fetch))
            statuses = session.scalars(select(CrawlRun.status).order_by(CrawlRun.id)).all()

        application = create_app(settings)
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/products")
        application.state.engine.dispose()

        assert first.status is RunStatus.COMPLETED
        assert second.status is RunStatus.UNCHANGED
        assert product_count == 1
        assert snapshot_count == 1
        assert fetch_count == 4
        assert statuses == [RunStatus.COMPLETED.value, RunStatus.UNCHANGED.value]
        assert response.status_code == 200
        assert response.json()["count"] == 1
        assert response.json()["items"][0]["fetch_id"] == 2
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_category_discovery_creates_bounded_child_watch_targets(settings: Settings) -> None:
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    service = CrawlService(
        settings,
        session_factory,
        lambda: FakeAdapter(build_listing_with_categories()),
    )
    try:
        result = await service.crawl(CrawlLimits(products=20))

        with session_factory() as session:
            targets = session.scalars(select(WatchTarget).order_by(WatchTarget.id)).all()

        assert result.status is RunStatus.COMPLETED
        assert [target.label for target in targets] == ["Bebek Arabaları", "Bebek Gıdaları"]
        assert targets[0].category == "Anne / Bebek / Oyuncak > Bebek Arabaları"
        assert targets[0].source_name == "hepsiburada"
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_category_only_page_can_expand_without_product_cards(settings: Settings) -> None:
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    service = CrawlService(
        settings,
        session_factory,
        lambda: FakeAdapter(build_category_only_listing()),
    )
    try:
        result = await service.crawl(CrawlLimits(products=20))

        with session_factory() as session:
            target_count = session.scalar(select(func.count()).select_from(WatchTarget))
            product_count = session.scalar(select(func.count()).select_from(Product))

        assert result.status is RunStatus.COMPLETED
        assert target_count == 2
        assert product_count == 0
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_detail_and_reviews_are_persisted_with_review_idempotency(
    settings: Settings,
) -> None:
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    service = CrawlService(
        settings,
        session_factory,
        lambda: FakeAdapter(build_listing(), build_detail()),
    )
    try:
        first = await service.crawl(CrawlLimits(products=1, details=1))
        second = await service.crawl(CrawlLimits(products=1, details=1))

        with session_factory() as session:
            detail_count = session.scalar(select(func.count()).select_from(ProductDetail))
            review_count = session.scalar(select(func.count()).select_from(Review))
            product = session.scalar(select(Product))

        assert first.details_created == 1
        assert first.reviews_created == 1
        assert second.details_created == 1
        assert second.reviews_created == 0
        assert detail_count == 2
        assert review_count == 1
        assert product is not None
        assert product.brand == "Canlı Marka"
        assert product.canonical_url.endswith("HBCV0000000001")
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_watchlist_refreshes_due_product_detail(settings: Settings) -> None:
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    service = CrawlService(
        settings,
        session_factory,
        lambda: FakeAdapter(build_listing(), build_detail()),
    )
    try:
        await service.crawl(CrawlLimits(products=1))
        with session_factory() as session:
            product = session.scalar(select(Product))
            assert product is not None
            product_id = product.id
            product_url = product.canonical_url
        target = add_watch_target(
            session_factory,
            WatchTargetInput(
                target_type="product",
                label="Öncelikli canlı ürün",
                source_url=product_url,
                category="Anne / Bebek / Oyuncak",
                priority=5,
                refresh_interval_hours=1,
            ),
        )
        with session_factory.begin() as session:
            stored_target = session.get_one(WatchTarget, target.id)
            stored_target.last_checked_at = datetime(2020, 1, 1, tzinfo=UTC)

        result = await WatchlistMonitor(session_factory, service).refresh_due(limit=1)

        with session_factory() as session:
            detail_count = session.scalar(select(func.count()).select_from(ProductDetail))
            review_count = session.scalar(select(func.count()).select_from(Review))
            stored_target = session.get_one(WatchTarget, target.id)

        assert result.queued == 1
        assert result.refreshed == 1
        assert result.stopped is False
        assert result.items[0].product_id == product_id
        assert detail_count == 1
        assert review_count == 1
        assert stored_target.last_status == "completed"
        assert stored_target.last_checked_at is not None
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_watchlist_discovers_and_links_new_product_url(settings: Settings) -> None:
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    detail = build_detail()
    service = CrawlService(
        settings,
        session_factory,
        lambda: FakeAdapter(build_listing(), detail),
    )
    try:
        target = add_watch_target(
            session_factory,
            WatchTargetInput(
                target_type="product",
                label="Yeni keşfedilecek ürün",
                source_url=detail.canonical_url,
                category="Anne / Bebek / Oyuncak",
                priority=5,
                refresh_interval_hours=1,
            ),
        )

        result = await WatchlistMonitor(session_factory, service).refresh_due(limit=1)

        with session_factory() as session:
            stored_target = session.get_one(WatchTarget, target.id)
            product = session.get_one(Product, stored_target.product_id)
            snapshot_count = session.scalar(select(func.count()).select_from(ProductSnapshot))

        assert result.queued == 1
        assert result.refreshed == 1
        assert result.items[0].product_id == product.id
        assert product.external_id == "HBCV0000000001"
        assert stored_target.last_status == "completed"
        assert snapshot_count == 1
    finally:
        engine.dispose()
