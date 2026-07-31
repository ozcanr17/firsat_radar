from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class PolicyState(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    DENIED = "policy_denied"
    UNAVAILABLE = "policy_unavailable"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    UNCHANGED = "unchanged"
    BLOCKED = "blocked"
    POLICY_DENIED = "policy_denied"
    POLICY_UNAVAILABLE = "policy_unavailable"
    PARSER_DRIFT = "parser_drift"
    FAILED = "failed"


@dataclass(frozen=True)
class CrawlLimits:
    products: int
    details: int = 0
    pages: int = 1

    def validate(self) -> None:
        if not 1 <= self.products <= 60:
            raise ValueError("Product limit must be between 1 and 60")
        if not 0 <= self.details <= 20:
            raise ValueError("Detail limit must be between 0 and 20")
        if not 1 <= self.pages <= 40:
            raise ValueError("Page limit must be between 1 and 40")


@dataclass(frozen=True)
class PolicyDecision:
    state: PolicyState
    url: str
    checked_at: datetime
    status_code: int | None
    content: str
    content_hash: str
    cached: bool
    reason_code: str | None = None

    @property
    def allowed(self) -> bool:
        return self.state is PolicyState.ALLOWED


@dataclass(frozen=True)
class ProductStub:
    external_id: str
    source_url: str
    title: str
    price: Decimal | None
    old_price: Decimal | None
    rating: float | None
    review_count: int | None
    rank: int
    image_url: str | None
    delivery_text: str | None
    coverage: float
    confidence: float


@dataclass(frozen=True)
class ListingResult:
    url: str
    fetched_at: datetime
    status_code: int | None
    content_hash: str
    raw_html: str
    products: tuple[ProductStub, ...]
    candidate_count: int
    coverage: float
    parser_version: str


@dataclass(frozen=True)
class FetchedDocument:
    url: str
    fetched_at: datetime
    status_code: int | None
    content_hash: str
    raw_html: str
    parser_version: str
    coverage: float
    confidence: float


@dataclass(frozen=True)
class ReviewStub:
    source_review_id: str
    rating: float | None
    review_date: datetime | None
    text_redacted: str
    source_url: str


@dataclass(frozen=True)
class ProductDetailResult:
    listing_external_id: str
    canonical_url: str
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
    detail_document: FetchedDocument
    reviews: tuple[ReviewStub, ...]
    review_document: FetchedDocument | None


@dataclass(frozen=True)
class CrawlSummary:
    run_id: int
    status: RunStatus
    products_seen: int
    products_created: int
    products_updated: int
    snapshots_created: int
    details_created: int
    reviews_created: int
    fetches_created: int
    error_code: str | None
    listing_signature: str | None


class SourceAccessError(RuntimeError):
    def __init__(self, status: RunStatus, error_code: str) -> None:
        super().__init__(error_code)
        self.status = status
        self.error_code = error_code


class ParserDriftError(RuntimeError):
    pass
