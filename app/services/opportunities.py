import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

from app.db.models import Analysis, Opportunity, Product
from app.db.session import SessionFactory


@dataclass(frozen=True)
class OpportunityView:
    product_id: int
    title: str
    source_url: str
    as_of: datetime
    score: float
    pattern: str | None
    demand: float | None
    satisfaction: float | None
    pain: float | None
    momentum: float | None
    price_position: float | None
    coverage: float
    confidence: float
    reasons: list[dict[str, object]]
    risks: list[str]
    hypothesis: dict[str, object]
    model_version: str


def list_latest_opportunities(
    session_factory: SessionFactory,
    limit: int = 60,
) -> list[OpportunityView]:
    latest_analysis_id = (
        select(func.max(Analysis.id))
        .where(Analysis.product_id == Product.id)
        .correlate(Product)
        .scalar_subquery()
    )
    query = (
        select(Product, Analysis, Opportunity)
        .join(Analysis, Analysis.id == latest_analysis_id)
        .join(Opportunity, Opportunity.analysis_id == Analysis.id)
        .order_by(Opportunity.score.desc(), Product.id.asc())
        .limit(limit)
    )
    with session_factory() as session:
        rows = session.execute(query).all()
    return [
        OpportunityView(
            product_id=product.id,
            title=product.title,
            source_url=product.canonical_url,
            as_of=analysis.as_of,
            score=opportunity.score,
            pattern=opportunity.pattern,
            demand=analysis.demand,
            satisfaction=analysis.satisfaction,
            pain=analysis.pain,
            momentum=analysis.momentum,
            price_position=analysis.price_position,
            coverage=analysis.coverage,
            confidence=analysis.confidence,
            reasons=json.loads(opportunity.reasons_json),
            risks=json.loads(opportunity.risks_json),
            hypothesis=json.loads(opportunity.hypothesis_json),
            model_version=opportunity.model_version,
        )
        for product, analysis, opportunity in rows
    ]
