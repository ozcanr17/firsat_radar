from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, func, select

from app.db.models import Product, ProductDetail, ProductSnapshot, Review
from app.db.session import SessionFactory


@dataclass(frozen=True)
class ProductView:
    id: int
    title: str
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


def latest_products_query() -> Select[
    tuple[Product, ProductSnapshot, float | None, float | None, int]
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
    return (
        select(
            Product,
            ProductSnapshot,
            ProductDetail.coverage,
            ProductDetail.confidence,
            stored_review_count,
        )
        .join(ProductSnapshot, ProductSnapshot.id == latest_snapshot_id)
        .outerjoin(ProductDetail, ProductDetail.id == latest_detail_id)
        .order_by(ProductSnapshot.rank.asc(), Product.id.asc())
    )


def list_latest_products(session_factory: SessionFactory, limit: int = 60) -> list[ProductView]:
    with session_factory() as session:
        rows = session.execute(latest_products_query().limit(limit)).all()
    return [
        ProductView(
            id=product.id,
            title=product.title,
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
        )
        for product, snapshot, detail_coverage, detail_confidence, stored_review_count in rows
    ]
