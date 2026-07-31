from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, func, select

from app.db.models import Analysis, Opportunity, Product, ProductDetail, ProductSnapshot, Review
from app.db.session import SessionFactory


@dataclass(frozen=True)
class ProductView:
    id: int
    title: str
    brand: str | None
    category: str | None
    source_url: str
    image_url: str | None
    observed_at: datetime
    fetch_id: int
    price: Decimal | None
    rating: float | None
    review_count: int | None
    rank: int | None
    coverage: float
    confidence: float
    detail_coverage: float | None
    detail_confidence: float | None
    stored_review_count: int
    opportunity_score: float | None
    opportunity_pattern: str | None
    analysis_confidence: float | None


def latest_products_query() -> Select[
    tuple[
        Product,
        ProductSnapshot,
        float | None,
        float | None,
        int,
        float | None,
        str | None,
        float | None,
    ]
]:
    latest_snapshot_id = (
        select(func.max(ProductSnapshot.id))
        .where(ProductSnapshot.product_id == Product.id)
        .correlate(Product)
        .scalar_subquery()
    )
    latest_detail_id = (
        select(func.max(ProductDetail.id))
        .where(ProductDetail.product_id == Product.id)
        .correlate(Product)
        .scalar_subquery()
    )
    stored_review_count = (
        select(func.count(Review.id))
        .where(Review.product_id == Product.id)
        .correlate(Product)
        .scalar_subquery()
    )
    latest_analysis_id = (
        select(func.max(Analysis.id))
        .where(Analysis.product_id == Product.id)
        .correlate(Product)
        .scalar_subquery()
    )
    return (
        select(
            Product,
            ProductSnapshot,
            ProductDetail.coverage,
            ProductDetail.confidence,
            stored_review_count,
            Opportunity.score,
            Opportunity.pattern,
            Analysis.confidence,
        )
        .join(ProductSnapshot, ProductSnapshot.id == latest_snapshot_id)
        .outerjoin(ProductDetail, ProductDetail.id == latest_detail_id)
        .outerjoin(Analysis, Analysis.id == latest_analysis_id)
        .outerjoin(Opportunity, Opportunity.analysis_id == Analysis.id)
        .order_by(ProductSnapshot.rank.asc(), Product.id.asc())
    )


def list_latest_products(session_factory: SessionFactory, limit: int = 60) -> list[ProductView]:
    with session_factory() as session:
        rows = session.execute(latest_products_query().limit(limit)).all()
    return [
        ProductView(
            id=product.id,
            title=product.title,
            brand=product.brand,
            category=product.category,
            source_url=product.canonical_url,
            image_url=product.image_url,
            observed_at=snapshot.observed_at,
            fetch_id=snapshot.fetch_id,
            price=snapshot.price,
            rating=snapshot.rating,
            review_count=snapshot.review_count,
            rank=snapshot.rank,
            coverage=snapshot.coverage,
            confidence=snapshot.confidence,
            detail_coverage=detail_coverage,
            detail_confidence=detail_confidence,
            stored_review_count=stored_review_count,
            opportunity_score=opportunity_score,
            opportunity_pattern=opportunity_pattern,
            analysis_confidence=analysis_confidence,
        )
        for (
            product,
            snapshot,
            detail_coverage,
            detail_confidence,
            stored_review_count,
            opportunity_score,
            opportunity_pattern,
            analysis_confidence,
        ) in rows
    ]
