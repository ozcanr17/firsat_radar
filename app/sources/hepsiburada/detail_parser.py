import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.crawl import ReviewStub

DETAIL_FIELDS = (
    "title",
    "brand",
    "seller",
    "description",
    "attributes",
    "review_url",
)
MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "eylül": 9,
    "ekim": 10,
    "kasım": 11,
    "aralık": 12,
}


@dataclass(frozen=True)
class RenderedProductDetail:
    title: str
    brand: str | None
    seller: str | None
    description: str | None
    product_info_text: str
    review_url: str | None


@dataclass(frozen=True)
class ParsedProductDetail:
    title: str
    brand: str | None
    seller: str | None
    description: str | None
    attributes: dict[str, str]
    origin: str | None
    overseas_sale: str | None
    stock: str | None
    review_url: str | None
    coverage: float
    confidence: float
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class RenderedReview:
    date_text: str | None
    text: str


def parse_product_detail(detail: RenderedProductDetail) -> ParsedProductDetail:
    title = normalize_text(detail.title)
    brand = normalize_optional(detail.brand)
    seller = normalize_optional(detail.seller)
    description = normalize_optional(detail.description)
    review_url = normalize_optional(detail.review_url)
    attributes = parse_attributes(detail.product_info_text)
    values = {
        "title": title,
        "brand": brand,
        "seller": seller,
        "description": description,
        "attributes": attributes,
        "review_url": review_url,
    }
    missing = tuple(f"missing_{field}" for field in DETAIL_FIELDS if not values[field])
    coverage = (len(DETAIL_FIELDS) - len(missing)) / len(DETAIL_FIELDS)
    return ParsedProductDetail(
        title=title,
        brand=brand,
        seller=seller,
        description=description,
        attributes=attributes,
        origin=attributes.get("Menşei"),
        overseas_sale=attributes.get("Yurt Dışı Satış"),
        stock=attributes.get("Stok Adedi"),
        review_url=review_url,
        coverage=coverage,
        confidence=coverage,
        reason_codes=missing,
    )


def parse_attributes(product_info_text: str) -> dict[str, str]:
    lines = [normalize_text(line) for line in product_info_text.splitlines()]
    lines = [line for line in lines if line]
    labels = {
        "Ağırlık Kapasitesi",
        "CE Uygunluk Sembolu",
        "Ebatlar",
        "Emniyet Kemeri Tipi",
        "Garanti Süresi (Ay)",
        "Kullanım Talimatı/Uyarıları",
        "Materyal",
        "Menşei",
        "Montaj Tipi",
        "Paket Görseli (arka)",
        "Paket Görseli (ön)",
        "Paket İçeriği",
        "Stok Adedi",
        "Stok Kodu",
        "Yurt Dışı Satış",
        "Üretici Bilgisi",
    }
    attributes: dict[str, str] = {}
    for index, line in enumerate(lines[:-1]):
        if line not in labels:
            continue
        value = lines[index + 1]
        if value not in labels and value not in {".", "Diğer", "Ürün özellikleri"}:
            attributes[line] = value
    return attributes


def parse_reviews(
    reviews: list[RenderedReview],
    product_url: str,
    review_url: str,
    observed_at: datetime,
) -> tuple[ReviewStub, ...]:
    parsed: list[ReviewStub] = []
    seen: set[str] = set()
    for rendered in reviews:
        text = redact_review_text(rendered.text)
        if not text:
            continue
        review_date = parse_review_date(rendered.date_text, observed_at)
        identity = "|".join(
            (product_url, review_date.isoformat() if review_date else "", normalize_identity(text))
        )
        source_review_id = hashlib.sha256(identity.encode()).hexdigest()
        if source_review_id in seen:
            continue
        seen.add(source_review_id)
        parsed.append(
            ReviewStub(
                source_review_id=source_review_id,
                rating=None,
                review_date=review_date,
                text_redacted=text,
                source_url=review_url,
            )
        )
    return tuple(parsed)


def parse_review_date(value: str | None, observed_at: datetime) -> datetime | None:
    if not value:
        return None
    match = re.search(r"(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)", value)
    if match is None:
        return None
    month = MONTHS.get(match.group(2).casefold())
    if month is None:
        return None
    candidate = datetime(observed_at.year, month, int(match.group(1)), tzinfo=UTC)
    if candidate > observed_at:
        candidate = candidate.replace(year=candidate.year - 1)
    return candidate


def redact_review_text(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[E-POSTA]", text, flags=re.I)
    text = re.sub(
        r"(?<!\d)(?:\+?90\s*)?(?:0?5\d{2})[\s.-]*\d{3}[\s.-]*\d{2}[\s.-]*\d{2}(?!\d)",
        "[TELEFON]",
        text,
    )
    text = re.sub(r"(?<!\d)\d{11}(?!\d)", "[KİMLİK]", text)
    return normalize_text(text)


def build_review_evidence(reviews: tuple[ReviewStub, ...]) -> str:
    rows = "".join(
        f'<article data-review-id="{review.source_review_id}">'
        f"<time>{html.escape(review.review_date.isoformat() if review.review_date else '')}</time>"
        f"<p>{html.escape(review.text_redacted)}</p></article>"
        for review in reviews
    )
    return f'<main data-identity-redacted="true">{rows}</main>'


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_text(value)
    return normalized or None


def normalize_identity(value: str) -> str:
    return normalize_text(value).casefold()
