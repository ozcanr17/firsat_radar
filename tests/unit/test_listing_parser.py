from decimal import Decimal

import pytest

from app.domain.crawl import ParserDriftError
from app.sources.hepsiburada.parser import (
    RenderedCategoryLink,
    RenderedProductCard,
    extract_external_id,
    parse_cards,
    parse_category_links,
    parse_price,
    parse_rating,
)


def test_turkish_price_is_normalized() -> None:
    assert parse_price("Sepete ekle, fiyat: 10.499,90 TL") == Decimal("10499.90")


def test_rating_and_review_count_are_normalized() -> None:
    assert parse_rating("Ürün puanı 4.8, 1.234 değerlendirme") == (4.8, 1234)


def test_external_product_id_is_extracted() -> None:
    assert extract_external_id("https://www.hepsiburada.com/urun-p-HBCV0000123ABC") == (
        "HBCV0000123ABC"
    )


def test_cards_are_parsed_with_coverage() -> None:
    cards = [
        RenderedProductCard(
            href="/urun-p-HBCV0000123ABC?magaza=x",
            title="Gerçek Ürün",
            accessible_text="Sepete ekle, fiyat: 1.249,90 TL",
            visible_text="Ürün puanı 4.6, 328 değerlendirme",
            image_url="https://images.example/product.jpg",
            delivery_text="Yarın kargoda",
        )
    ]

    products, coverage = parse_cards(cards, "https://www.hepsiburada.com", 20)

    assert coverage == 1.0
    assert products[0].source_url == "https://www.hepsiburada.com/urun-p-HBCV0000123ABC"
    assert products[0].price == Decimal("1249.90")
    assert products[0].review_count == 328


def test_empty_listing_triggers_parser_drift() -> None:
    with pytest.raises(ParserDriftError, match="listing_has_no_product_candidates"):
        parse_cards([], "https://www.hepsiburada.com", 20)


def test_category_links_are_bounded_deduplicated_and_same_marketplace() -> None:
    links = parse_category_links(
        [
            RenderedCategoryLink(
                href="/bebek-arabalari-c-600001",
                label="  Bebek Arabaları ",
            ),
            RenderedCategoryLink(
                href="https://www.hepsiburada.com/bebek-arabalari-c-600001?tracking=x",
                label="Tekrar",
            ),
            RenderedCategoryLink(
                href="https://example.com/bebek-c-9",
                label="Dış bağlantı",
            ),
        ],
        "https://www.hepsiburada.com",
        "https://www.hepsiburada.com/anne-bebek-oyuncak-c-2147483639",
    )

    assert len(links) == 1
    assert links[0].label == "Bebek Arabaları"
    assert links[0].url == "https://www.hepsiburada.com/bebek-arabalari-c-600001"
