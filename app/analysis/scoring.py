from collections.abc import Sequence
from decimal import Decimal

from app.domain.analysis import MetricSet, OpportunityResult, ProductAnalysisInput

MODEL_VERSION = "rules-tr-v1"
WEIGHTS = {
    "demand": 0.25,
    "satisfaction": 0.20,
    "pain": 0.25,
    "momentum": 0.15,
    "price_position": 0.15,
}


def calculate_metrics(
    item: ProductAnalysisInput,
    review_population: Sequence[int],
    price_population: Sequence[Decimal],
) -> MetricSet:
    demand = percentile(float(item.review_count), review_population) if item.review_count else None
    satisfaction = clamp(item.rating * 20.0) if item.rating is not None else None
    pain = (
        clamp(item.negative_review_count / item.stored_review_count * 100.0)
        if item.stored_review_count
        else None
    )
    momentum = calculate_momentum(
        item.review_count,
        item.previous_review_count,
        item.price,
        item.previous_price,
    )
    price_position = (
        100.0 - percentile(float(item.price), price_population) if item.price is not None else None
    )
    values = (demand, satisfaction, pain, momentum, price_position)
    coverage = sum(value is not None for value in values) / len(values)
    detail_quality = item.detail_confidence or 0.0
    review_quality = min(item.stored_review_count / 10.0, 1.0)
    evidence_quality = item.listing_confidence * 0.5 + detail_quality * 0.2 + review_quality * 0.3
    confidence = clamp(coverage * evidence_quality * 100.0) / 100.0
    return MetricSet(
        demand=round_optional(demand),
        satisfaction=round_optional(satisfaction),
        pain=round_optional(pain),
        momentum=round_optional(momentum),
        price_position=round_optional(price_position),
        coverage=round(coverage, 4),
        confidence=round(confidence, 4),
    )


def score_opportunity(
    item: ProductAnalysisInput,
    metrics: MetricSet,
    market_size: int,
) -> OpportunityResult:
    values = {
        "demand": metrics.demand,
        "satisfaction": metrics.satisfaction,
        "pain": metrics.pain,
        "momentum": metrics.momentum,
        "price_position": metrics.price_position,
    }
    available_weight = sum(WEIGHTS[name] for name, value in values.items() if value is not None)
    raw_score = (
        sum(WEIGHTS[name] * value for name, value in values.items() if value is not None)
        / available_weight
        if available_weight
        else 0.0
    )
    score = raw_score * metrics.confidence + 50.0 * (1.0 - metrics.confidence)
    pattern = resolve_pattern(metrics)
    reasons = build_reasons(item, metrics)
    risks = build_risks(item, metrics, market_size)
    return OpportunityResult(
        score=round(clamp(score), 2),
        pattern=pattern,
        reasons=reasons,
        risks=risks,
        hypothesis={
            "summary": hypothesis_for(pattern),
            "model": MODEL_VERSION,
            "requires_validation": True,
        },
    )


def percentile(value: float, population: Sequence[int] | Sequence[Decimal]) -> float:
    numeric = [float(candidate) for candidate in population]
    if not numeric:
        return 50.0
    if len(numeric) == 1:
        return 50.0
    lower = sum(candidate < value for candidate in numeric)
    equal = sum(candidate == value for candidate in numeric)
    return clamp((lower + (equal - 1) * 0.5) / (len(numeric) - 1) * 100.0)


def calculate_momentum(
    review_count: int | None,
    previous_review_count: int | None,
    price: Decimal | None,
    previous_price: Decimal | None,
) -> float | None:
    signals = []
    weights = []
    if review_count is not None and previous_review_count is not None:
        growth = max(review_count - previous_review_count, 0) / max(previous_review_count, 1)
        signals.append(min(growth, 1.0) * 100.0)
        weights.append(0.7)
    if price is not None and previous_price is not None and previous_price > 0:
        reduction = max(float(previous_price - price) / float(previous_price), 0.0)
        signals.append(min(reduction, 1.0) * 100.0)
        weights.append(0.3)
    if not signals:
        return None
    return sum(value * weight for value, weight in zip(signals, weights, strict=True)) / sum(
        weights
    )


def resolve_pattern(metrics: MetricSet) -> str:
    if at_least(metrics.demand, 60.0) and at_least(metrics.pain, 30.0):
        return "validated_pain"
    if at_least(metrics.satisfaction, 80.0) and at_least(metrics.demand, 50.0):
        return "validated_demand"
    if at_least(metrics.price_position, 70.0):
        return "price_advantage"
    if at_least(metrics.momentum, 60.0):
        return "early_momentum"
    return "watch"


def build_reasons(
    item: ProductAnalysisInput,
    metrics: MetricSet,
) -> tuple[dict[str, object], ...]:
    facts: dict[str, object] = {
        "demand": {"review_count": item.review_count},
        "satisfaction": {"rating": item.rating},
        "pain": {
            "negative_reviews": item.negative_review_count,
            "stored_reviews": item.stored_review_count,
        },
        "momentum": {
            "previous_review_count": item.previous_review_count,
            "previous_price": str(item.previous_price) if item.previous_price is not None else None,
        },
        "price_position": {"price": str(item.price) if item.price is not None else None},
    }
    values = {
        "demand": metrics.demand,
        "satisfaction": metrics.satisfaction,
        "pain": metrics.pain,
        "momentum": metrics.momentum,
        "price_position": metrics.price_position,
    }
    return tuple(
        {"metric": name, "score": value, "evidence": facts[name]}
        for name, value in values.items()
        if value is not None
    )


def build_risks(
    item: ProductAnalysisInput,
    metrics: MetricSet,
    market_size: int,
) -> tuple[str, ...]:
    risks = []
    if metrics.confidence < 0.7:
        risks.append("low_confidence")
    if item.stored_review_count < 10:
        risks.append("sparse_review_sample")
    if metrics.momentum is None:
        risks.append("momentum_unavailable")
    if market_size < 5:
        risks.append("small_market_sample")
    return tuple(risks)


def hypothesis_for(pattern: str) -> str:
    return {
        "validated_pain": "Talep doğrulanmış; tekrarlanan sorunlar iyileştirme alanı gösterebilir.",
        "validated_demand": "Talep ve memnuniyet birlikte güçlü görünüyor.",
        "price_advantage": "Kategori içi fiyat konumu rekabet avantajı sağlayabilir.",
        "early_momentum": "Son snapshot değişimleri erken ivme sinyali veriyor.",
        "watch": "Mevcut kanıt güçlü bir fırsat deseni için henüz yeterli değil.",
    }[pattern]


def at_least(value: float | None, threshold: float) -> bool:
    return value is not None and value >= threshold


def round_optional(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def clamp(value: float) -> float:
    return max(0.0, min(100.0, value))
