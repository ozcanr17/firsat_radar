from decimal import Decimal

from app.analysis.scoring import calculate_metrics, percentile, score_opportunity
from app.domain.analysis import ProductAnalysisInput


def build_input() -> ProductAnalysisInput:
    return ProductAnalysisInput(
        product_id=1,
        source_url="https://www.hepsiburada.com/urun-p-HBCV1",
        fetch_id=2,
        price=Decimal("90.00"),
        previous_price=Decimal("100.00"),
        rating=4.6,
        review_count=100,
        previous_review_count=80,
        listing_confidence=1.0,
        detail_confidence=1.0,
        stored_review_count=10,
        negative_review_count=3,
    )


def test_percentile_handles_market_position_and_ties() -> None:
    assert percentile(10, [10]) == 50.0
    assert percentile(20, [10, 20, 30]) == 50.0
    assert percentile(20, [20, 20, 30]) == 25.0


def test_metrics_and_opportunity_are_deterministic() -> None:
    item = build_input()
    metrics = calculate_metrics(
        item,
        [10, 100, 500],
        [Decimal("50"), Decimal("90"), Decimal("100")],
    )
    result = score_opportunity(item, metrics, market_size=3)

    assert metrics.demand == 50.0
    assert metrics.satisfaction == 92.0
    assert metrics.pain == 30.0
    assert metrics.momentum == 20.5
    assert metrics.price_position == 50.0
    assert metrics.coverage == 1.0
    assert metrics.confidence == 1.0
    assert result.score == 48.98
    assert result.pattern == "validated_demand"
    assert result.risks == ("small_market_sample",)
