from decimal import Decimal

import pytest

from app.services.commerce import (
    BusinessCaseInput,
    calculate_unit_economics,
    normalize_hepsiburada_url,
    normalize_marketplace_url,
)


def business_case() -> BusinessCaseInput:
    return BusinessCaseInput(
        purchase_cost=Decimal("100"),
        commission_rate=0.2,
        shipping_cost=Decimal("20"),
        packaging_cost=Decimal("5"),
        advertising_rate=0.03,
        return_rate=0.02,
        tax_rate=0,
        other_cost=Decimal("5"),
        target_margin_rate=0.2,
        monthly_units=10,
        notes=None,
    )


def test_unit_economics_produces_go_no_go_and_break_even() -> None:
    profitable = calculate_unit_economics(Decimal("250"), business_case())
    unprofitable = calculate_unit_economics(Decimal("150"), business_case())

    assert profitable.contribution == Decimal("57.50")
    assert profitable.margin_rate == 0.23
    assert profitable.break_even_price == Decimal("173.33")
    assert profitable.target_sale_price == Decimal("236.36")
    assert profitable.monthly_contribution == Decimal("575.00")
    assert profitable.decision == "go"
    assert unprofitable.decision == "no_go"


def test_target_url_is_canonicalized_and_restricted() -> None:
    assert (
        normalize_hepsiburada_url("https://hepsiburada.com/urun-p-HBCV1?magaza=test#yorum")
        == "https://www.hepsiburada.com/urun-p-HBCV1"
    )

    with pytest.raises(ValueError, match="invalid_hepsiburada_url"):
        normalize_hepsiburada_url("https://example.com/urun-p-HBCV1")

    with pytest.raises(ValueError, match="forbidden_target_url"):
        normalize_hepsiburada_url("https://www.hepsiburada.com/product-comment/urun")


def test_multimarket_urls_are_canonicalized_to_registered_hosts() -> None:
    assert (
        normalize_marketplace_url("amazon_tr", "https://amazon.com.tr/example?tag=test")
        == "https://www.amazon.com.tr/example"
    )
    assert (
        normalize_marketplace_url(
            "amazon_tr",
            "https://www.amazon.com.tr/gp/browse.html?node=12466208031&ref_=nav_baby",
        )
        == "https://www.amazon.com.tr/gp/browse.html?node=12466208031"
    )
    assert (
        normalize_marketplace_url("trendyol", "https://www.trendyol.com/example#reviews")
        == "https://www.trendyol.com/example"
    )

    with pytest.raises(ValueError, match="invalid_marketplace_url"):
        normalize_marketplace_url("mediamarkt_tr", "https://example.com/product")
