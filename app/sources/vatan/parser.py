import re
from dataclasses import dataclass
from decimal import Decimal
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from app.domain.crawl import CategoryLink, MerchantOffer, ParserDriftError, ProductStub
from app.sources.akakce.parser import (
    find_product_document,
    load_json_ld,
    parse_decimal,
    parse_int,
    parse_price,
    parse_rating,
)

BASE_URL = "https://www.vatanbilgisayar.com"
MARKETPLACE_LABEL = "Vatan Bilgisayar"
PRODUCT_PATH_PATTERN = re.compile(r"^/[a-z0-9][a-z0-9\-]*\.html$")
CATEGORY_PATH_PATTERN = re.compile(r"^/[a-z0-9][a-z0-9\-]*/$")
LISTING_PARSER_VERSION = "vatan-listing-v1"
DETAIL_PARSER_VERSION = "vatan-detail-v1"
PRODUCT_CARD_SELECTOR = ".product-list .product-list__content"


@dataclass(frozen=True)
class ParsedProductDetail:
    title: str
    brand: str | None
    category_path: str | None
    description: str | None
    attributes: dict[str, str]
    price: Decimal | None
    availability: str | None
    rating: float | None
    review_count: int | None
    image_url: str | None
    offers: tuple[MerchantOffer, ...]
    coverage: float
    confidence: float
    reason_codes: tuple[str, ...]


def normalize_url(base_url: str, href: str) -> str:
    parts = urlsplit(urljoin(base_url, href))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def extract_external_id(url: str) -> str | None:
    path = urlsplit(url).path
    if not PRODUCT_PATH_PATTERN.match(path):
        return None
    return path.removeprefix("/").removesuffix(".html")[:160]


def parse_listing(
    html: str,
    current_url: str,
    limit: int,
) -> tuple[tuple[ProductStub, ...], float, int]:
    soup = BeautifulSoup(html, "lxml")
    cards = [node for node in soup.select(PRODUCT_CARD_SELECTOR) if isinstance(node, Tag)]
    seen: set[str] = set()
    products: list[ProductStub] = []
    candidates = 0
    for card in cards:
        if len(products) >= limit:
            break
        link = card.find("a", href=True) or card.find_parent("a", href=True)
        if not isinstance(link, Tag):
            continue
        source_url = normalize_url(current_url, str(link.get("href")))
        external_id = extract_external_id(source_url)
        if external_id is not None and external_id in seen:
            continue
        candidates += 1
        heading = card.select_one(".product-list__product-name h3, .product-list__product-name")
        title = " ".join(heading.get_text(" ", strip=True).split()) if heading else ""
        if not external_id or not title:
            continue
        seen.add(external_id)
        price_node = card.select_one(".product-list__price")
        price = parse_price(price_node.get_text(" ", strip=True)) if price_node else None
        rating_node = card.select_one(".product-card-bottom__score")
        rating = parse_rating(rating_node.get_text(strip=True)) if rating_node else None
        image = card.find("img")
        image_url = None
        if isinstance(image, Tag):
            raw_image = image.get("data-src") or image.get("src")
            image_url = str(raw_image) if raw_image else None
        present = sum(value is not None for value in (price, image_url, rating))
        products.append(
            ProductStub(
                external_id=external_id,
                source_url=source_url,
                title=title[:1000],
                price=price,
                old_price=None,
                rating=rating,
                review_count=None,
                rank=len(products) + 1,
                image_url=image_url,
                delivery_text=None,
                coverage=(3 + present) / 5,
                confidence=1.0 if price is not None else 0.6,
                seller_count=1,
            )
        )
    if not candidates:
        return (), 0.0, 0
    coverage = len(products) / candidates
    if coverage < 0.7:
        raise ParserDriftError("listing_parser_coverage_below_70_percent")
    return tuple(products), coverage, candidates


def parse_category_links(html: str, current_url: str, limit: int) -> tuple[CategoryLink, ...]:
    soup = BeautifulSoup(html, "lxml")
    seen = {normalize_url(BASE_URL, current_url)}
    results: list[CategoryLink] = []
    for link in soup.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        url = normalize_url(current_url, str(link.get("href")))
        parts = urlsplit(url)
        if (parts.hostname or "").removeprefix("www.") != "vatanbilgisayar.com":
            continue
        if not CATEGORY_PATH_PATTERN.match(parts.path) or url in seen:
            continue
        label = " ".join(link.get_text(" ", strip=True).split())
        if not label:
            continue
        seen.add(url)
        results.append(CategoryLink(label=label[:255], url=url))
        if len(results) >= limit:
            break
    return tuple(results)


def offer_from_document(document: dict[str, Any], canonical_url: str) -> MerchantOffer | None:
    offers = document.get("offers")
    entry = offers[0] if isinstance(offers, list) and offers else offers
    if not isinstance(entry, dict):
        return None
    availability = entry.get("availability")
    return MerchantOffer(
        marketplace=MARKETPLACE_LABEL,
        seller=MARKETPLACE_LABEL,
        price=parse_decimal(entry.get("price")),
        currency=str(entry.get("priceCurrency") or "TRY")[:8],
        availability=str(availability).rsplit("/", 1)[-1][:40] if availability else None,
        offer_url=str(entry.get("url") or canonical_url)[:2048],
    )


def parse_product_detail(html: str, canonical_url: str) -> ParsedProductDetail:
    soup = BeautifulSoup(html, "lxml")
    document = find_product_document(load_json_ld(soup))
    if document is None:
        raise ParserDriftError("detail_structured_data_missing")
    heading = soup.find("h1")
    title = " ".join(
        unescape(
            str(document.get("name") or (heading.get_text(" ", strip=True) if heading else ""))
        ).split()
    )
    if not title:
        raise ParserDriftError("detail_title_missing")
    brand = document.get("brand")
    brand_name = str(brand.get("name")).strip() if isinstance(brand, dict) else None
    offer = offer_from_document(document, canonical_url)
    rating_block = document.get("aggregateRating")
    rating = (
        parse_rating(rating_block.get("ratingValue")) if isinstance(rating_block, dict) else None
    )
    review_count = (
        parse_int(rating_block.get("reviewCount") or rating_block.get("ratingCount"))
        if isinstance(rating_block, dict)
        else None
    )
    image = document.get("image")
    image_url = image[0] if isinstance(image, list) and image else image
    category_path = (
        unescape(str(document.get("category"))).strip() if document.get("category") else None
    )
    description = (
        unescape(str(document.get("description"))).strip() if document.get("description") else None
    )
    attributes: dict[str, str] = {}
    for key, label in (("sku", "sku"), ("mpn", "mpn"), ("model", "model"), ("color", "renk")):
        value = document.get(key)
        if value:
            attributes[label] = str(value)[:255]
    if category_path:
        attributes["kategori"] = category_path[:255]
    reason_codes: list[str] = []
    if offer is None or offer.price is None:
        reason_codes.append("offer_price_unavailable")
    if rating is None:
        reason_codes.append("source_rating_unavailable")
    reason_codes.append("source_reviews_not_collected")
    present = sum(
        value is not None
        for value in (brand_name, offer.price if offer else None, image_url, category_path)
    )
    return ParsedProductDetail(
        title=title[:1000],
        brand=brand_name[:255] if brand_name else None,
        category_path=category_path[:500] if category_path else None,
        description=description[:4000] if description else None,
        attributes=attributes,
        price=offer.price if offer else None,
        availability=offer.availability if offer else None,
        rating=rating,
        review_count=review_count,
        image_url=str(image_url)[:2048] if image_url else None,
        offers=(offer,) if offer else (),
        coverage=(1 + present) / 5,
        confidence=1.0 if offer and offer.price is not None else 0.5,
        reason_codes=tuple(reason_codes),
    )
