from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Self

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import CrawlRun, Fetch, Product, ProductSnapshot
from app.db.session import build_engine, build_session_factory
from app.domain.crawl import (
    CrawlLimits,
    ListingResult,
    PolicyDecision,
    PolicyState,
    ProductStub,
    RunStatus,
)
from app.main import create_app
from app.services.crawl import CrawlService


class FakeAdapter:
    def __init__(self, listing: ListingResult) -> None:
        self.listing = listing

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
