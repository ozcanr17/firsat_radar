import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from app.domain.crawl import CategoryLink, MerchantOffer, ParserDriftError, ProductStub

BASE_URL = "https://www.akakce.com"
PRODUCT_ID_PATTERN = re.compile(r",(\d{4,})\.html$")
CATEGORY_PATH_PATTERN = re.compile(r"^/[a-z0-9][a-z0-9\-]*\.html$")
STOCK_PATTERN = re.compile(r"(\d+)\s*adet", re.IGNORECASE)
LISTING_PARSER_VERSION = "akakce-listing-v1"
DETAIL_PARSER_VERSION = "akakce-detail-v1"


@dataclass(frozen=True)
class ParsedProductDetail:
    title: str
    brand: str | None
    category_path: str | None
    description: str | None
    attributes: dict[str, str]
    seller_count: int | None
    price: Decimal | None
    high_price: Decimal | None
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
    match = PRODUCT_ID_PATTERN.search(urlsplit(url).path)
    return match.group(1) if match else None


def parse_price(value: str) -> Decimal | None:
    digits = re.sub(r"[^\d,.]", "", value.replace(" ", ""))
    if not digits:
        return None
    normalized = digits.replace(".", "").replace(",", ".")
    try:
        price = Decimal(normalized)
    except InvalidOperation:
        return None
    return price if price > 0 else None


def parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        price = Decimal(str(value).strip())
    except InvalidOperation:
        return None
    return price if price > 0 else None


def parse_int(value: object) -> int | None:
    try:
        number = int(str(value).strip().replace(".", ""))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def parse_rating(value: object) -> float | None:
    try:
        rating = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return rating if 0 <= rating <= 5 else None


def load_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not isinstance(node, Tag):
            continue
        try:
            payload = json.loads(node.get_text())
        except (json.JSONDecodeError, ValueError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if isinstance(candidate, dict):
                documents.append(candidate)
    return documents


def find_product_document(documents: list[dict[str, Any]]) -> dict[str, Any] | None:
    for document in documents:
        types = document.get("@type")
        names = types if isinstance(types, list) else [types]
        if any(name in {"Product", "ProductGroup"} for name in names):
            return document
    return None


def parse_listing(
    html: str,
    current_url: str,
    limit: int,
) -> tuple[tuple[ProductStub, ...], float, int]:
    soup = BeautifulSoup(html, "lxml")
    items = [node for node in soup.select("li[data-pr]") if isinstance(node, Tag)]
    seen: set[str] = set()
    products: list[ProductStub] = []
    candidates = 0
    for node in items:
        if len(products) >= limit:
            break
        link = node.find("a", href=True)
        if not isinstance(link, Tag):
            continue
        candidates += 1
        external_id = str(node.get("data-pr") or "").strip()
        href = str(link.get("href") or "")
        source_url = normalize_url(current_url, href)
        title = " ".join(str(link.get("title") or link.get_text(" ", strip=True)).split())
        if not external_id or not title or extract_external_id(source_url) != external_id:
            continue
        if external_id in seen:
            continue
        seen.add(external_id)
        price_node = node.select_one("span.pt_v8")
        price = parse_price(price_node.get_text(" ", strip=True)) if price_node else None
        image = node.find("img")
        image_url = str(image.get("src")) if isinstance(image, Tag) and image.get("src") else None
        seller_count = parse_int(node.get("data-cp"))
        present = sum(value is not None for value in (price, image_url, seller_count))
        products.append(
            ProductStub(
                external_id=external_id,
                source_url=source_url,
                title=title[:1000],
                price=price,
                old_price=None,
                rating=None,
                review_count=None,
                rank=len(products) + 1,
                image_url=image_url,
                delivery_text=None,
                coverage=(3 + present) / 6,
                confidence=1.0 if price is not None else 0.6,
                seller_count=seller_count,
            )
        )
    if not candidates:
        return (), 0.0, 0
    coverage = len(products) / candidates
    if coverage < 0.7:
        raise ParserDriftError("listing_parser_coverage_below_70_percent")
    return tuple(products), coverage, candidates


def parse_category_links(
    html: str,
    current_url: str,
    limit: int,
) -> tuple[CategoryLink, ...]:
    soup = BeautifulSoup(html, "lxml")
    current = normalize_url(BASE_URL, current_url)
    seen = {current}
    results: list[CategoryLink] = []
    for link in soup.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue
        url = normalize_url(current_url, str(link.get("href")))
        parts = urlsplit(url)
        if (parts.hostname or "").removeprefix("www.") != "akakce.com":
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


def parse_offers(document: dict[str, Any]) -> tuple[tuple[MerchantOffer, ...], Decimal | None]:
    aggregate = document.get("offers")
    if not isinstance(aggregate, dict):
        return (), None
    entries = aggregate.get("offers")
    raw_offers = entries if isinstance(entries, list) else []
    offers: list[MerchantOffer] = []
    for entry in raw_offers:
        if not isinstance(entry, dict):
            continue
        seller = entry.get("seller")
        seller_name = str(seller.get("name", "")).strip() if isinstance(seller, dict) else ""
        marketplace, _, storefront = seller_name.partition("/")
        availability = entry.get("availability")
        offers.append(
            MerchantOffer(
                marketplace=(marketplace or "bilinmiyor").strip()[:120],
                seller=storefront.strip()[:500] or None,
                price=parse_decimal(entry.get("price")),
                currency=str(entry.get("priceCurrency") or "TRY")[:8],
                availability=str(availability).rsplit("/", 1)[-1][:40] if availability else None,
                offer_url=str(entry.get("url"))[:2048] if entry.get("url") else None,
            )
        )
    return tuple(offers), parse_decimal(aggregate.get("highPrice"))


def merge_visible_offer_details(
    soup: BeautifulSoup,
    offers: tuple[MerchantOffer, ...],
) -> tuple[MerchantOffer, ...]:
    visible: dict[str, tuple[str | None, str | None]] = {}
    for node in soup.select("ul#PL > li"):
        if not isinstance(node, Tag):
            continue
        price_node = node.select_one("span.pt_v8")
        price = parse_price(price_node.get_text(" ", strip=True)) if price_node else None
        if price is None:
            continue
        stock_node = node.select_one("span.stock_v8")
        delivery_node = node.select_one("span.sd_v8")
        visible[str(price)] = (
            " ".join(stock_node.get_text(" ", strip=True).split()) if stock_node else None,
            " ".join(delivery_node.get_text(" ", strip=True).split()) if delivery_node else None,
        )
    merged: list[MerchantOffer] = []
    for offer in offers:
        stock_text, delivery_text = visible.get(str(offer.price), (None, None))
        merged.append(
            MerchantOffer(
                marketplace=offer.marketplace,
                seller=offer.seller,
                price=offer.price,
                currency=offer.currency,
                availability=offer.availability,
                offer_url=offer.offer_url,
                delivery_text=delivery_text,
                stock_text=stock_text,
            )
        )
    return tuple(merged)


def parse_product_detail(html: str) -> ParsedProductDetail:
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
    offers, high_price = parse_offers(document)
    offers = merge_visible_offer_details(soup, offers)
    aggregate = document.get("offers")
    offer_count = (
        parse_int(aggregate.get("offerCount")) if isinstance(aggregate, dict) else None
    ) or (len(offers) or None)
    low_price = parse_decimal(aggregate.get("lowPrice")) if isinstance(aggregate, dict) else None
    prices = [offer.price for offer in offers if offer.price is not None]
    price = low_price or (min(prices) if prices else None)
    high = high_price or (max(prices) if prices else None)
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
    image_url = str(image[0]) if isinstance(image, list) and image else None
    if isinstance(image, str):
        image_url = image
    category_path = (
        unescape(str(document.get("category"))).strip() if document.get("category") else None
    )
    description = (
        unescape(str(document.get("description"))).strip() if document.get("description") else None
    )
    attributes: dict[str, str] = {}
    if document.get("sku"):
        attributes["sku"] = str(document["sku"])[:255]
    if category_path:
        attributes["kategori"] = category_path[:255]
    if offer_count is not None:
        attributes["satici_sayisi"] = str(offer_count)
    reason_codes: list[str] = []
    if not offers:
        reason_codes.append("merchant_offers_unavailable")
    if rating is None:
        reason_codes.append("source_rating_unavailable")
    reason_codes.append("source_reviews_not_published")
    present = sum(
        value is not None for value in (brand_name, price, high, image_url, category_path)
    )
    coverage = (1 + present) / 6
    return ParsedProductDetail(
        title=title[:1000],
        brand=brand_name[:255] if brand_name else None,
        category_path=category_path[:500] if category_path else None,
        description=description[:4000] if description else None,
        attributes=attributes,
        seller_count=offer_count,
        price=price,
        high_price=high,
        rating=rating,
        review_count=review_count,
        image_url=image_url[:2048] if image_url else None,
        offers=offers,
        coverage=coverage,
        confidence=1.0 if price is not None else 0.5,
        reason_codes=tuple(reason_codes),
    )
