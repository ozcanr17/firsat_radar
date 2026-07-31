from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ReviewSignal:
    topic: str
    polarity: str
    severity: str
    confidence: float
    evidence_span: str


@dataclass(frozen=True)
class MetricSet:
    demand: float | None
    satisfaction: float | None
    pain: float | None
    momentum: float | None
    price_position: float | None
    coverage: float
    confidence: float


@dataclass(frozen=True)
class ProductAnalysisInput:
    product_id: int
    source_url: str
    fetch_id: int
    price: Decimal | None
    previous_price: Decimal | None
    rating: float | None
    review_count: int | None
    previous_review_count: int | None
    listing_confidence: float
    detail_confidence: float | None
    stored_review_count: int
    negative_review_count: int


@dataclass(frozen=True)
class OpportunityResult:
    score: float
    pattern: str
    reasons: tuple[dict[str, object], ...]
    risks: tuple[str, ...]
    hypothesis: dict[str, object]


@dataclass(frozen=True)
class AnalysisSummary:
    products_seen: int
    analyses_created: int
    analyses_reused: int
    opportunities_created: int
    labels_created: int
    labels_updated: int
    model_version: str
