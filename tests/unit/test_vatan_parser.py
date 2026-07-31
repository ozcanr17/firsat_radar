import json

import pytest

from app.domain.crawl import ParserDriftError
from app.sources.vatan.parser import (
    extract_external_id,
    parse_category_links,
    parse_listing,
    parse_product_detail,
)

LISTING_HTML = """
<html><body>
<a href="/notebook/">Notebook</a>
<a href="/cep-telefonu/">Telefon</a>
<div class="product-list">
  <a class="product-list-link" href="https://www.vatanbilgisayar.com/lenovo-loq-i7.html">
    <div class="product-list__content">
      <div class="product-list__product-name"><h3>Lenovo LOQ Core i7 RTX5060</h3></div>
      <div class="product-list__cost"><span class="product-list__price">74.999</span></div>
      <div class="product-card-bottom"><span class="product-card-bottom__score">4,6</span></div>
    </div>
  </a>
  <div class="product-list__content">
    <a href="https://www.vatanbilgisayar.com/casper-nirvana-s100.html">
      <div class="product-list__product-name"><h3>Casper Nirvana S100</h3></div>
    </a>
    <div class="product-list__cost"><span class="product-list__price">34.999</span></div>
  </div>
</div>
</body></html>
"""

PRODUCT_DOCUMENT = {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Lenovo Ideapad Slim 3 Core i5",
    "sku": "150531",
    "mpn": "83K10016TR",
    "model": "Ideapad Slim 3",
    "color": "Gri",
    "category": "Bilgisayar > Notebook > Laptop",
    "image": ["https://www.vatanbilgisayar.com/img/lenovo.jpg"],
    "brand": {"@type": "Brand", "name": "LENOVO"},
    "offers": {
        "@type": "Offer",
        "url": "https://www.vatanbilgisayar.com/lenovo-ideapad-slim-3.html",
        "price": "29999",
        "priceCurrency": "TRY",
        "availability": "https://schema.org/InStock",
    },
    "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.71", "reviewCount": "249"},
}

DETAIL_HTML = f"""
<html><body><h1>Lenovo Ideapad Slim 3</h1>
<script type="application/ld+json">{json.dumps(PRODUCT_DOCUMENT)}</script>
</body></html>
"""

LISTING_URL = "https://www.vatanbilgisayar.com/notebook/"
DETAIL_URL = "https://www.vatanbilgisayar.com/lenovo-ideapad-slim-3.html"


def test_extract_external_id_uses_product_slug() -> None:
    assert extract_external_id(DETAIL_URL) == "lenovo-ideapad-slim-3"
    assert extract_external_id(LISTING_URL) is None


def test_parse_listing_resolves_links_from_card_or_ancestor() -> None:
    products, coverage, candidates = parse_listing(LISTING_HTML, LISTING_URL, 60)

    assert candidates == 2
    assert coverage == 1.0
    assert [product.external_id for product in products] == [
        "lenovo-loq-i7",
        "casper-nirvana-s100",
    ]
    assert str(products[0].price) == "74999"
    assert products[0].rating == 4.6
    assert products[0].seller_count == 1


def test_parse_listing_deduplicates_repeated_cards() -> None:
    duplicated = LISTING_HTML.replace("</div>\n</body>", "</div>\n</body>")
    products, _, _ = parse_listing(duplicated + LISTING_HTML, LISTING_URL, 60)

    assert len({product.external_id for product in products}) == len(products)


def test_parse_category_links_keeps_only_category_paths() -> None:
    links = parse_category_links(LISTING_HTML, LISTING_URL, 40)

    urls = {link.url for link in links}
    assert "https://www.vatanbilgisayar.com/cep-telefonu/" in urls
    assert LISTING_URL not in urls
    assert all(not link.url.endswith(".html") for link in links)


def test_parse_product_detail_reads_identity_and_offer() -> None:
    detail = parse_product_detail(DETAIL_HTML, DETAIL_URL)

    assert detail.title == "Lenovo Ideapad Slim 3 Core i5"
    assert detail.brand == "LENOVO"
    assert str(detail.price) == "29999"
    assert detail.availability == "InStock"
    assert detail.rating == 4.71
    assert detail.review_count == 249
    assert detail.attributes["mpn"] == "83K10016TR"
    assert detail.attributes["sku"] == "150531"
    assert len(detail.offers) == 1
    assert detail.offers[0].marketplace == "Vatan Bilgisayar"


def test_parse_product_detail_marks_reviews_as_not_collected() -> None:
    detail = parse_product_detail(DETAIL_HTML, DETAIL_URL)

    assert "source_reviews_not_collected" in detail.reason_codes


def test_parse_product_detail_requires_structured_data() -> None:
    with pytest.raises(ParserDriftError):
        parse_product_detail("<html><body><h1>Ürün</h1></body></html>", DETAIL_URL)
