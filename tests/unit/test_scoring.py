from dataclasses import replace
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
    assert result.score == 48.97
    assert result.pattern == "validated_demand"
    assert result.risks == ("small_market_sample", "single_offer_no_spread")


def test_spread_metric_uses_observed_merchant_offers() -> None:
    item = build_input()
    with_offers = replace(
        item,
        offer_prices=(Decimal("37999.00"), Decimal("45599.05"), Decimal("45839.05")),
        marketplaces=("Hepsiburada", "Pttavm", "idefix"),
        seller_count=3,
    )
    metrics = calculate_metrics(with_offers, [10, 100, 500], [Decimal("50")])

    assert metrics.spread == 17.1


def test_single_offer_yields_no_spread_and_keeps_coverage() -> None:
    item = replace(build_input(), offer_prices=(Decimal("100"),), marketplaces=("Vatan",))
    metrics = calculate_metrics(
        item,
        [10, 100, 500],
        [Decimal("50"), Decimal("90"), Decimal("100")],
    )

    assert metrics.spread is None
    assert metrics.coverage == 1.0


def test_wide_spread_across_marketplaces_is_flagged_as_arbitrage() -> None:
    item = replace(
        build_input(),
        offer_prices=(Decimal("37999.00"), Decimal("45839.05")),
        marketplaces=("Hepsiburada", "Pttavm"),
        seller_count=2,
    )
    metrics = calculate_metrics(item, [10, 100, 500], [Decimal("50")])
    result = score_opportunity(item, metrics, market_size=10)

    assert result.pattern == "price_arbitrage"
    evidence = next(reason["evidence"] for reason in result.reasons if reason["metric"] == "spread")
    assert evidence == {
        "lowest_offer": "37999.00",
        "highest_offer": "45839.05",
        "offer_count": 2,
        "marketplaces": ["Hepsiburada", "Pttavm"],
    }
    assert "single_offer_no_spread" not in result.risks


def test_spread_inside_one_marketplace_is_risk_flagged() -> None:
    item = replace(
        build_input(),
        offer_prices=(Decimal("100"), Decimal("140")),
        marketplaces=("Hepsiburada",),
        seller_count=2,
    )
    metrics = calculate_metrics(item, [10, 100, 500], [Decimal("50")])
    result = score_opportunity(item, metrics, market_size=10)

    assert "spread_within_single_marketplace" in result.risks


def test_missing_offers_are_reported_as_risk() -> None:
    item = build_input()
    metrics = calculate_metrics(item, [10, 100, 500], [Decimal("50")])
    result = score_opportunity(item, metrics, market_size=10)

    assert metrics.spread is None
    assert "single_offer_no_spread" in result.risks
