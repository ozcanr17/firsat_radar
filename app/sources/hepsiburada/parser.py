import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.domain.crawl import ParserDriftError, ProductStub

PRODUCT_CODE_PATTERN = re.compile(r"-(?:p|pm)-([A-Z0-9]+)", re.IGNORECASE)
PRICE_PATTERN = re.compile(r"fiyat:\s*([\d.]+(?:,\d{1,2})?)\s*TL", re.IGNORECASE)
RATING_PATTERN = re.compile(
    r"Ürün puanı\s*([0-5](?:[.,]\d+)?)\s*,\s*([\d.]+)\s*değerlendirme",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RenderedProductCard:
    href: str
    title: str
    accessible_text: str
    visible_text: str
    image_url: str | None
    delivery_text: str | None


def normalize_url(base_url: str, href: str) -> str:
    absolute = urljoin(base_url, href)
    parts = urlsplit(absolute)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def parse_price(value: str) -> Decimal | None:
    match = PRICE_PATTERN.search(value)
    if not match:
        return None
    normalized = match.group(1).replace(".", "").replace(",", ".")
    try:
        price = Decimal(normalized)
    except InvalidOperation:
        return None
    return price if price >= 0 else None


def parse_rating(value: str) -> tuple[float | None, int | None]:
    match = RATING_PATTERN.search(value)
    if not match:
        return None, None
    rating = float(match.group(1).replace(",", "."))
    review_count = int(match.group(2).replace(".", ""))
    if not 0 <= rating <= 5 or review_count < 0:
        return None, None
    return rating, review_count


def extract_external_id(url: str) -> str | None:
    match = PRODUCT_CODE_PATTERN.search(url)
    return match.group(1).upper() if match else None


def card_to_product(
    card: RenderedProductCard,
    base_url: str,
    rank: int,
) -> ProductStub | None:
    title = " ".join(card.title.split())
    source_url = normalize_url(base_url, card.href)
    external_id = extract_external_id(source_url)
    if not title or not external_id or not source_url.startswith("https://www.hepsiburada.com/"):
        return None
    combined_text = f"{card.accessible_text} {card.visible_text}"
    price = parse_price(combined_text)
    rating, review_count = parse_rating(combined_text)
    present_fields = sum(
        value is not None for value in (title, source_url, external_id, price, rating, review_count)
    )
    coverage = present_fields / 6
    confidence = 1.0 if price is not None else 0.75
    return ProductStub(
        external_id=external_id,
        source_url=source_url,
        title=title,
        price=price,
        old_price=None,
        rating=rating,
        review_count=review_count,
        rank=rank,
        image_url=card.image_url,
        delivery_text=card.delivery_text,
        coverage=coverage,
        confidence=confidence,
    )


def parse_cards(
    cards: list[RenderedProductCard],
    base_url: str,
    limit: int,
) -> tuple[tuple[ProductStub, ...], float]:
    parsed = tuple(
        product
        for rank, card in enumerate(cards[:limit], start=1)
        if (product := card_to_product(card, base_url, rank)) is not None
    )
    candidate_count = min(len(cards), limit)
    coverage = len(parsed) / candidate_count if candidate_count else 0.0
    if not candidate_count:
        raise ParserDriftError("listing_has_no_product_candidates")
    if coverage < 0.7:
        raise ParserDriftError("listing_parser_coverage_below_70_percent")
    return parsed, coverage
