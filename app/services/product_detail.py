import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.db.models import Product, ProductDetail, ProductSnapshot, Review, ReviewLabel
from app.db.session import SessionFactory
from app.services.commerce import BusinessCaseView, get_business_case
from app.services.opportunities import OpportunityView, list_latest_opportunities
from app.services.products import ProductView, list_latest_products


@dataclass(frozen=True)
class SnapshotView:
    observed_at: datetime
    price: Decimal | None
    old_price: Decimal | None
    rating: float | None
    review_count: int | None
    stock: str | None


@dataclass(frozen=True)
class ReviewLabelView:
    topic: str
    polarity: str
    severity: str
    confidence: float
    evidence_span: str


@dataclass(frozen=True)
class ReviewView:
    review_date: datetime | None
    observed_at: datetime
    text: str
    source_url: str
    labels: tuple[ReviewLabelView, ...]


@dataclass(frozen=True)
class PainClusterView:
    topic: str
    negative_count: int
    high_severity_count: int
    share: float


@dataclass(frozen=True)
class ProductPageView:
    product: ProductView
    description: str | None
    attributes: tuple[tuple[str, str], ...]
    origin: str | None
    overseas_sale: str | None
    stock: str | None
    review_url: str | None
    detail_reason_codes: tuple[str, ...]
    snapshots: tuple[SnapshotView, ...]
    reviews: tuple[ReviewView, ...]
    opportunity: OpportunityView | None
    pain_clusters: tuple[PainClusterView, ...]
    business_case: BusinessCaseView | None


def get_product_page(
    session_factory: SessionFactory,
    product_id: int,
) -> ProductPageView | None:
    product_view = next(
        (product for product in list_latest_products(session_factory) if product.id == product_id),
        None,
    )
    if product_view is None:
        return None
    opportunity = next(
        (
            candidate
            for candidate in list_latest_opportunities(session_factory)
            if candidate.product_id == product_id
        ),
        None,
    )
    with session_factory() as session:
        product = session.get(Product, product_id)
        if product is None:
            return None
        detail = session.scalar(
            select(ProductDetail)
            .where(ProductDetail.product_id == product_id)
            .order_by(ProductDetail.observed_at.desc(), ProductDetail.id.desc())
            .limit(1)
        )
        snapshots = session.scalars(
            select(ProductSnapshot)
            .where(ProductSnapshot.product_id == product_id)
            .order_by(ProductSnapshot.observed_at.asc(), ProductSnapshot.id.asc())
        ).all()
        reviews = session.scalars(
            select(Review)
            .where(Review.product_id == product_id)
            .order_by(Review.review_date.desc(), Review.id.desc())
        ).all()
        review_views = []
        cluster_counts: dict[str, list[int]] = {}
        for review in reviews:
            labels = session.scalars(
                select(ReviewLabel)
                .where(ReviewLabel.review_id == review.id)
                .order_by(ReviewLabel.topic)
            ).all()
            review_views.append(
                ReviewView(
                    review_date=review.review_date,
                    observed_at=review.observed_at,
                    text=review.text_redacted,
                    source_url=review.source_url,
                    labels=tuple(
                        ReviewLabelView(
                            topic=label.topic,
                            polarity=label.polarity,
                            severity=label.severity,
                            confidence=label.confidence,
                            evidence_span=label.evidence_span,
                        )
                        for label in labels
                    ),
                )
            )
            for label in labels:
                if label.polarity != "negative":
                    continue
                counts = cluster_counts.setdefault(label.topic, [0, 0])
                counts[0] += 1
                counts[1] += label.severity == "high"
    attributes = json.loads(detail.attributes_json) if detail else {}
    reason_codes = json.loads(detail.reason_codes_json) if detail else []
    return ProductPageView(
        product=product_view,
        description=detail.description_text if detail else None,
        attributes=tuple(sorted(attributes.items())),
        origin=detail.origin if detail else None,
        overseas_sale=detail.overseas_sale if detail else None,
        stock=detail.stock if detail else None,
        review_url=detail.review_url if detail else None,
        detail_reason_codes=tuple(reason_codes),
        snapshots=tuple(
            SnapshotView(
                observed_at=snapshot.observed_at,
                price=snapshot.price,
                old_price=snapshot.old_price,
                rating=snapshot.rating,
                review_count=snapshot.review_count,
                stock=snapshot.stock,
            )
            for snapshot in snapshots
        ),
        reviews=tuple(review_views),
        opportunity=opportunity,
        pain_clusters=tuple(
            PainClusterView(
                topic=topic,
                negative_count=counts[0],
                high_severity_count=counts[1],
                share=round(counts[0] / len(reviews), 4) if reviews else 0.0,
            )
            for topic, counts in sorted(
                cluster_counts.items(),
                key=lambda item: (-item[1][0], item[0]),
            )
        ),
        business_case=get_business_case(session_factory, product_id),
    )
