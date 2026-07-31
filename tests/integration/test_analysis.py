from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.config import Settings
from app.db.migrations import upgrade_database
from app.db.models import (
    Analysis,
    CrawlRun,
    Fetch,
    Opportunity,
    Product,
    ProductDetail,
    ProductSnapshot,
    Review,
    ReviewLabel,
    Source,
)
from app.db.session import build_engine, build_session_factory
from app.main import create_app
from app.services.analysis import AnalysisService


@pytest.mark.asyncio
async def test_analysis_is_traceable_and_idempotent(settings: Settings) -> None:
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    observed_at = datetime.now(UTC)
    with session_factory.begin() as session:
        source = Source(
            name="hepsiburada",
            base_url="https://www.hepsiburada.com",
            enabled=True,
            policy_state="allowed",
        )
        session.add(source)
        session.flush()
        run = CrawlRun(source_id=source.id, status="completed", counts_json="{}")
        session.add(run)
        session.flush()
        listing_fetch = Fetch(
            run_id=run.id,
            url="https://www.hepsiburada.com/category",
            fetched_at=observed_at,
            status_code=200,
            content_hash="listing",
            parser_version="test-v1",
            coverage=1.0,
            debug_metadata_json="{}",
        )
        detail_fetch = Fetch(
            run_id=run.id,
            url="https://www.hepsiburada.com/urun-p-HBCV1",
            fetched_at=observed_at,
            status_code=200,
            content_hash="detail",
            parser_version="test-v1",
            coverage=1.0,
            debug_metadata_json="{}",
        )
        session.add_all((listing_fetch, detail_fetch))
        session.flush()
        product = Product(
            source_id=source.id,
            external_id="HBCV1",
            canonical_url=detail_fetch.url,
            title="Gerçek Ürün",
            last_fetch_id=detail_fetch.id,
            last_seen_at=observed_at,
        )
        session.add(product)
        session.flush()
        session.add_all(
            (
                ProductSnapshot(
                    product_id=product.id,
                    fetch_id=listing_fetch.id,
                    observed_at=observed_at,
                    price=Decimal("100"),
                    rating=4.5,
                    review_count=50,
                    rank=1,
                    coverage=1.0,
                    confidence=1.0,
                ),
                ProductDetail(
                    product_id=product.id,
                    fetch_id=detail_fetch.id,
                    observed_at=observed_at,
                    attributes_json="{}",
                    coverage=1.0,
                    confidence=1.0,
                    reason_codes_json="[]",
                ),
                Review(
                    product_id=product.id,
                    fetch_id=detail_fetch.id,
                    source_review_id="a" * 64,
                    text_redacted="Ürün kırık geldi ve iade ettim.",
                    source_url=f"{detail_fetch.url}-yorumlari",
                    observed_at=observed_at,
                ),
                Review(
                    product_id=product.id,
                    fetch_id=detail_fetch.id,
                    source_review_id="b" * 64,
                    text_redacted="Paketleme güzel ve ürün sağlam.",
                    source_url=f"{detail_fetch.url}-yorumlari",
                    observed_at=observed_at,
                ),
            )
        )

    service = AnalysisService(session_factory)
    first = service.analyze()
    second = service.analyze()

    with session_factory() as session:
        analysis_count = session.scalar(select(func.count()).select_from(Analysis))
        opportunity_count = session.scalar(select(func.count()).select_from(Opportunity))
        label_count = session.scalar(select(func.count()).select_from(ReviewLabel))

    application = create_app(settings)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/opportunities")
        dashboard = await client.get("/")
        products_page = await client.get("/products", params={"q": "Gerçek", "sort": "reviews"})
        product_page = await client.get(f"/products/{product.id}")
        opportunities_page = await client.get("/opportunities")
        recommendations_page = await client.get("/recommendations")
        business_case = await client.put(
            f"/api/v1/business-cases/{product.id}",
            json={
                "purchase_cost": 40,
                "commission_rate": 0.15,
                "shipping_cost": 5,
                "packaging_cost": 2,
                "advertising_rate": 0.02,
                "return_rate": 0.03,
                "tax_rate": 0,
                "other_cost": 0,
                "target_margin_rate": 0.2,
                "monthly_units": 20,
            },
        )
        trade_desk = await client.get("/trade-desk")
        recommendations_with_economics = await client.get("/recommendations")
        runs_page = await client.get("/runs")
        settings_page = await client.get("/settings")
        products_csv = await client.get("/exports/products.csv")
        opportunities_csv = await client.get("/exports/opportunities.csv")
        stylesheet = await client.get("/static/styles.css")
    application.state.engine.dispose()
    engine.dispose()

    assert first.analyses_created == 1
    assert first.opportunities_created == 1
    assert first.labels_created > 0
    assert second.analyses_reused == 1
    assert second.labels_created == 0
    assert analysis_count == 1
    assert opportunity_count == 1
    assert label_count == first.labels_created
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["source_url"] == detail_fetch.url
    assert "Öne çıkan fırsatlar" in dashboard.text
    assert "Gerçek Ürün" in products_page.text
    assert "Ürün veya marka ara" in products_page.text
    assert "Fırsat kanıtı" in product_page.text
    assert "yüksek önem" in product_page.text
    assert "Gerçek maliyet girilmeden" in product_page.text
    assert "Fırsat radarları" in opportunities_page.text
    assert "Kanıttan aksiyona" in recommendations_page.text
    assert "Al-sat adayı" in recommendations_page.text
    assert business_case.status_code == 200
    assert business_case.json()["economics"]["decision"] == "go"
    assert business_case.json()["economics"]["contribution"] == "33.00"
    assert "Gerçek Ürün" in trade_desk.text
    assert "Birim katkı" in recommendations_with_economics.text
    assert "Tarama geçmişi" in runs_page.text
    assert "Katalog kapsamı" in settings_page.text
    assert products_csv.status_code == 200
    assert "product_id,title" in products_csv.text
    assert opportunities_csv.status_code == 200
    assert "product_id,title,score" in opportunities_csv.text
    assert stylesheet.status_code == 200
    assert ".app-shell" in stylesheet.text
