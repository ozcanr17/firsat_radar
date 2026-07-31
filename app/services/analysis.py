import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.review_labels import classify_review
from app.analysis.scoring import MODEL_VERSION, calculate_metrics, score_opportunity
from app.db.models import (
    Analysis as AnalysisModel,
)
from app.db.models import (
    Offer,
    Opportunity,
    Product,
    ProductDetail,
    ProductSnapshot,
    Review,
    ReviewLabel,
)
from app.db.session import SessionFactory
from app.domain.analysis import AnalysisSummary, ProductAnalysisInput, ReviewSignal


class AnalysisService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _latest_offers(
        session: Session,
        product_id: int,
    ) -> tuple[tuple[Decimal, ...], tuple[str, ...]]:
        latest_observed_at = session.scalar(
            select(Offer.observed_at)
            .where(Offer.product_id == product_id)
            .order_by(Offer.observed_at.desc(), Offer.id.desc())
            .limit(1)
        )
        if latest_observed_at is None:
            return (), ()
        offers = session.scalars(
            select(Offer).where(
                Offer.product_id == product_id,
                Offer.observed_at == latest_observed_at,
            )
        ).all()
        prices = tuple(offer.price for offer in offers if offer.price is not None)
        marketplaces = tuple(
            sorted({offer.marketplace for offer in offers if offer.marketplace is not None})
        )
        return prices, marketplaces

    def analyze(self, limit: int = 200) -> AnalysisSummary:
        if not 1 <= limit <= 500:
            raise ValueError("Analysis limit must be between 1 and 500")
        with self.session_factory.begin() as session:
            current_analysis_exists = (
                select(AnalysisModel.id)
                .where(
                    AnalysisModel.product_id == Product.id,
                    AnalysisModel.fetch_id == Product.last_fetch_id,
                    AnalysisModel.model_version == MODEL_VERSION,
                )
                .exists()
            )
            products = session.scalars(
                select(Product)
                .order_by(current_analysis_exists, Product.last_seen_at.desc(), Product.id)
                .limit(limit)
            ).all()
            inputs = []
            labels_created = 0
            labels_updated = 0
            for product in products:
                snapshots = session.scalars(
                    select(ProductSnapshot)
                    .where(ProductSnapshot.product_id == product.id)
                    .order_by(ProductSnapshot.observed_at.desc(), ProductSnapshot.id.desc())
                    .limit(2)
                ).all()
                if not snapshots:
                    continue
                current = snapshots[0]
                previous = snapshots[1] if len(snapshots) > 1 else None
                detail_confidence = session.scalar(
                    select(ProductDetail.confidence)
                    .where(ProductDetail.product_id == product.id)
                    .order_by(ProductDetail.observed_at.desc(), ProductDetail.id.desc())
                    .limit(1)
                )
                offer_prices, marketplaces = self._latest_offers(session, product.id)
                reviews = session.scalars(
                    select(Review).where(Review.product_id == product.id).order_by(Review.id)
                ).all()
                negative_reviews = 0
                for review in reviews:
                    signals = classify_review(review.text_redacted)
                    if any(signal.polarity == "negative" for signal in signals):
                        negative_reviews += 1
                    created, updated = self._upsert_labels(session, review, signals)
                    labels_created += created
                    labels_updated += updated
                inputs.append(
                    ProductAnalysisInput(
                        product_id=product.id,
                        source_url=product.canonical_url,
                        fetch_id=product.last_fetch_id or current.fetch_id,
                        price=current.price,
                        previous_price=previous.price if previous else None,
                        rating=current.rating,
                        review_count=current.review_count,
                        previous_review_count=previous.review_count if previous else None,
                        listing_confidence=current.confidence,
                        detail_confidence=detail_confidence,
                        stored_review_count=len(reviews),
                        negative_review_count=negative_reviews,
                        offer_prices=offer_prices,
                        marketplaces=marketplaces,
                        seller_count=current.seller_count,
                    )
                )
            review_population = [
                item.review_count for item in inputs if item.review_count is not None
            ]
            price_population = [item.price for item in inputs if item.price is not None]
            analyses_created = 0
            analyses_reused = 0
            opportunities_created = 0
            for item in inputs:
                existing = session.scalar(
                    select(AnalysisModel).where(
                        AnalysisModel.product_id == item.product_id,
                        AnalysisModel.fetch_id == item.fetch_id,
                        AnalysisModel.model_version == MODEL_VERSION,
                    )
                )
                if existing is not None:
                    analyses_reused += 1
                    continue
                metrics = calculate_metrics(item, review_population, price_population)
                result = score_opportunity(item, metrics, len(inputs))
                analysis = AnalysisModel(
                    product_id=item.product_id,
                    fetch_id=item.fetch_id,
                    source_url=item.source_url,
                    as_of=datetime.now(UTC),
                    demand=metrics.demand,
                    satisfaction=metrics.satisfaction,
                    pain=metrics.pain,
                    momentum=metrics.momentum,
                    price_position=metrics.price_position,
                    price_spread=metrics.spread,
                    confidence=metrics.confidence,
                    coverage=metrics.coverage,
                    model_version=MODEL_VERSION,
                )
                session.add(analysis)
                session.flush()
                session.add(
                    Opportunity(
                        product_id=item.product_id,
                        analysis_id=analysis.id,
                        score=result.score,
                        pattern=result.pattern,
                        reasons_json=json.dumps(result.reasons, ensure_ascii=False),
                        risks_json=json.dumps(result.risks, ensure_ascii=False),
                        hypothesis_json=json.dumps(result.hypothesis, ensure_ascii=False),
                        model_version=MODEL_VERSION,
                    )
                )
                analyses_created += 1
                opportunities_created += 1
            return AnalysisSummary(
                products_seen=len(inputs),
                analyses_created=analyses_created,
                analyses_reused=analyses_reused,
                opportunities_created=opportunities_created,
                labels_created=labels_created,
                labels_updated=labels_updated,
                model_version=MODEL_VERSION,
            )

    @staticmethod
    def _upsert_labels(
        session: Session,
        review: Review,
        signals: tuple[ReviewSignal, ...],
    ) -> tuple[int, int]:
        created = 0
        updated = 0
        incoming_topics = {signal.topic for signal in signals}
        existing_labels = session.scalars(
            select(ReviewLabel).where(ReviewLabel.review_id == review.id)
        ).all()
        for existing in existing_labels:
            if existing.topic not in incoming_topics:
                session.delete(existing)
                updated += 1
        for signal in signals:
            label = session.scalar(
                select(ReviewLabel).where(
                    ReviewLabel.review_id == review.id,
                    ReviewLabel.topic == signal.topic,
                )
            )
            if label is None:
                session.add(
                    ReviewLabel(
                        review_id=review.id,
                        topic=signal.topic,
                        polarity=signal.polarity,
                        severity=signal.severity,
                        confidence=signal.confidence,
                        evidence_span=signal.evidence_span,
                    )
                )
                created += 1
                continue
            values = (
                label.polarity,
                label.severity,
                label.confidence,
                label.evidence_span,
            )
            incoming = (
                signal.polarity,
                signal.severity,
                signal.confidence,
                signal.evidence_span,
            )
            if values != incoming:
                label.polarity = signal.polarity
                label.severity = signal.severity
                label.confidence = signal.confidence
                label.evidence_span = signal.evidence_span
                updated += 1
        return created, updated
