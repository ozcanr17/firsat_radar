import json

import pytest

from app.domain.crawl import ParserDriftError
from app.sources.akakce.parser import (
    extract_external_id,
    parse_category_links,
    parse_listing,
    parse_product_detail,
)

LISTING_HTML = """
<html><body>
<a href="/laptop-notebook.html">Laptop ve Notebook</a>
<a href="/cep-telefonu.html">Cep Telefonu</a>
<a href="/laptop-notebook/en-ucuz-x-fiyati,111.html">urun</a>
<ul id="CPL">
  <li data-cp="91" data-pr="1277491339">
    <a href="/laptop-notebook/en-ucuz-asus-vivobook-fiyati,1277491339.html"
       title="Asus Vivobook 15 Notebook">
      <img src="https://cdn.akakce.com/x/asus/vivobook.jpg"/>
      <span class="pt_v8"> 23.334<i>,00 TL </i></span>
    </a>
  </li>
  <li data-cp="7" data-pr="882468581">
    <a href="/laptop-notebook/en-ucuz-macbook-air-fiyati,882468581.html"
       title="MacBook Air M1 13.3&quot;">
      <img src="https://cdn.akakce.com/x/apple/macbook.jpg"/>
      <span class="pt_v8"> 37.999<i>,00 TL </i></span>
    </a>
  </li>
</ul>
</body></html>
"""

PRODUCT_DOCUMENT = {
    "@context": "https://schema.org",
    "@type": "ProductGroup",
    "name": "MacBook Air M1 8 GB 256 GB SSD 13.3&quot; Uzay Grisi",
    "sku": "882468581",
    "category": "Elektronik > Bilgisayarlar > Laptop ve Notebook",
    "brand": {"@type": "Brand", "name": "Apple"},
    "image": ["https://cdn.akakce.com/x/apple/macbook.jpg"],
    "offers": {
        "@type": "AggregateOffer",
        "offerCount": "3",
        "lowPrice": "37999.00",
        "highPrice": "45839.05",
        "priceCurrency": "TRY",
        "offers": [
            {
                "@type": "Offer",
                "price": "45839.05",
                "priceCurrency": "TRY",
                "availability": "https://schema.org/InStock",
                "url": "https://www.pttavm.com/macbook-air-p-1",
                "seller": {"@type": "Organization", "name": "Pttavm/KAVASTECH"},
            },
            {
                "@type": "Offer",
                "price": "37999.00",
                "priceCurrency": "TRY",
                "availability": "https://schema.org/InStock",
                "url": "https://www.hepsiburada.com/macbook-air-p-2",
                "seller": {"@type": "Organization", "name": "Hepsiburada/Element Teknoloji"},
            },
            {
                "@type": "Offer",
                "price": "45599.05",
                "priceCurrency": "TRY",
                "availability": "https://schema.org/InStock",
                "url": "https://www.idefix.com/macbook-air-p-3",
                "seller": {"@type": "Organization", "name": "idefix/KAVASTECH"},
            },
        ],
    },
    "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.7", "reviewCount": "120"},
}

DETAIL_HTML = f"""
<html><body>
<h1>MacBook Air M1</h1>
<script type="application/ld+json">{json.dumps(PRODUCT_DOCUMENT)}</script>
<ul id="PL">
  <li><a>
    <span class="pt_v8">37.999<i>,00 TL</i></span>
    <span class="stock_v8">Stokta 10 adet</span>
    <span class="sd_v8">1 iş günü</span>
  </a></li>
</ul>
</body></html>
"""

LISTING_URL = "https://www.akakce.com/laptop-notebook.html"


def test_extract_external_id_reads_trailing_product_id() -> None:
    assert extract_external_id("https://www.akakce.com/x/en-ucuz-y-fiyati,882468581.html") == (
        "882468581"
    )
    assert extract_external_id("https://www.akakce.com/laptop-notebook.html") is None


def test_parse_listing_reads_price_and_seller_count() -> None:
    products, coverage, candidates = parse_listing(LISTING_HTML, LISTING_URL, 60)

    assert candidates == 2
    assert coverage == 1.0
    assert [product.external_id for product in products] == ["1277491339", "882468581"]
    assert str(products[0].price) == "23334.00"
    assert products[0].seller_count == 91
    assert products[1].seller_count == 7
    assert products[0].source_url.startswith("https://www.akakce.com/")


def test_parse_listing_respects_limit() -> None:
    products, _, _ = parse_listing(LISTING_HTML, LISTING_URL, 1)

    assert len(products) == 1


def test_parse_category_links_keeps_same_marketplace_categories() -> None:
    links = parse_category_links(LISTING_HTML, LISTING_URL, 40)

    urls = {link.url for link in links}
    assert "https://www.akakce.com/cep-telefonu.html" in urls
    assert LISTING_URL not in urls


def test_parse_category_links_excludes_product_pages() -> None:
    links = parse_category_links(LISTING_HTML, LISTING_URL, 40)

    assert all(extract_external_id(link.url) is None for link in links)


def test_parse_product_detail_reads_every_merchant_offer() -> None:
    detail = parse_product_detail(DETAIL_HTML)

    assert detail.title == 'MacBook Air M1 8 GB 256 GB SSD 13.3" Uzay Grisi'
    assert detail.brand == "Apple"
    assert detail.seller_count == 3
    assert str(detail.price) == "37999.00"
    assert str(detail.high_price) == "45839.05"
    assert detail.rating == 4.7
    assert detail.review_count == 120
    assert {offer.marketplace for offer in detail.offers} == {
        "Pttavm",
        "Hepsiburada",
        "idefix",
    }
    cheapest = min(detail.offers, key=lambda offer: offer.price or 0)
    assert cheapest.marketplace == "Hepsiburada"
    assert cheapest.seller == "Element Teknoloji"
    assert cheapest.stock_text == "Stokta 10 adet"
    assert cheapest.delivery_text == "1 iş günü"


def test_parse_product_detail_never_invents_reviews() -> None:
    detail = parse_product_detail(DETAIL_HTML)

    assert "source_reviews_not_published" in detail.reason_codes


def test_parse_product_detail_requires_structured_data() -> None:
    with pytest.raises(ParserDriftError):
        parse_product_detail("<html><body><h1>Ürün</h1></body></html>")
