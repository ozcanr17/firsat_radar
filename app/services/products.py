from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.engine import Row

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


@dataclass(frozen=True)
class ProductSearchResult:
    items: list[ProductView]
    total: int
    categories: list[str]


ProductRow = Row[
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
]


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
    return product_views(rows)


def search_products(
    session_factory: SessionFactory,
    query: str = "",
    category: str = "",
    sort: str = "rank",
    limit: int = 200,
) -> ProductSearchResult:
    statement = latest_products_query().order_by(None)
    normalized_query = query.strip()
    normalized_category = category.strip()
    if normalized_query:
        statement = statement.where(
            or_(
                Product.title.icontains(normalized_query, autoescape=True),
                Product.brand.icontains(normalized_query, autoescape=True),
            )
        )
    if normalized_category:
        statement = statement.where(Product.category == normalized_category)
    if sort == "newest":
        statement = statement.order_by(ProductSnapshot.observed_at.desc(), Product.id.desc())
    elif sort == "price_asc":
        statement = statement.order_by(ProductSnapshot.price.asc().nulls_last(), Product.id.asc())
    elif sort == "price_desc":
        statement = statement.order_by(ProductSnapshot.price.desc().nulls_last(), Product.id.asc())
    elif sort == "reviews":
        statement = statement.order_by(
            ProductSnapshot.review_count.desc().nulls_last(), Product.id.asc()
        )
    elif sort == "opportunity":
        statement = statement.order_by(Opportunity.score.desc().nulls_last(), Product.id.asc())
    else:
        statement = statement.order_by(ProductSnapshot.rank.asc().nulls_last(), Product.id.asc())
    with session_factory() as session:
        total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = session.execute(statement.limit(limit)).all()
        categories = [
            value
            for value in session.scalars(
                select(Product.category)
                .where(Product.category.is_not(None))
                .distinct()
                .order_by(Product.category)
            ).all()
            if value is not None
        ]
    return ProductSearchResult(
        items=product_views(rows),
        total=total,
        categories=categories,
    )


def product_views(rows: Sequence[ProductRow]) -> list[ProductView]:
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
