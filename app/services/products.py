from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, func, select

from app.db.models import Product, ProductSnapshot
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


def latest_products_query() -> Select[tuple[Product, ProductSnapshot]]:
    latest_snapshot_id = (
        select(func.max(ProductSnapshot.id))
        .where(ProductSnapshot.product_id == Product.id)
        .correlate(Product)
        .scalar_subquery()
    )
    return (
        select(Product, ProductSnapshot)
        .join(ProductSnapshot, ProductSnapshot.id == latest_snapshot_id)
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
        )
        for product, snapshot in rows
    ]
