import hashlib
from datetime import UTC, datetime

from app.config import Settings
from app.domain.crawl import (
    CrawlLimits,
    FetchedDocument,
    ListingResult,
    ProductDetailResult,
    ProductStub,
    RunStatus,
    SourceAccessError,
)
from app.sources.http_source import HttpSourceAdapter
from app.sources.vatan.parser import (
    BASE_URL,
    DETAIL_PARSER_VERSION,
    LISTING_PARSER_VERSION,
    MARKETPLACE_LABEL,
    parse_category_links,
    parse_listing,
    parse_product_detail,
)

USER_AGENT = "FirsatRadar/1.8 (+https://github.com/ozcanr17/firsat_radar)"
CRAWLER_TOKEN = "FirsatRadar"


class VatanHttpAdapter(HttpSourceAdapter):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            settings,
            base_url=BASE_URL,
            cache_prefix="vatan",
            user_agent=USER_AGENT,
            crawler_token=CRAWLER_TOKEN,
            min_request_seconds=settings.vatan_min_request_seconds,
            max_request_seconds=settings.vatan_max_request_seconds,
            cooldown_minutes=settings.vatan_rate_limit_cooldown_minutes,
            daily_request_limit=settings.vatan_daily_request_limit,
        )

    async def discover(self, start_url: str, limits: CrawlLimits) -> ListingResult:
        limits.validate()
        response = await self.request(start_url, "listing")
        raw_html = response.text
        current_url = str(response.url)
        category_links = parse_category_links(
            raw_html,
            current_url,
            self.settings.category_discovery_links_per_page,
        )
        products, coverage, candidates = parse_listing(raw_html, current_url, limits.products)
        if not products and not category_links:
            raise SourceAccessError(RunStatus.PARSER_DRIFT, "listing_has_no_candidates")
        return ListingResult(
            url=current_url,
            fetched_at=datetime.now(UTC),
            status_code=response.status_code,
            content_hash=hashlib.sha256(raw_html.encode()).hexdigest(),
            raw_html=raw_html,
            products=products,
            candidate_count=candidates,
            coverage=coverage if products else 1.0,
            parser_version=LISTING_PARSER_VERSION,
            category_links=category_links,
        )

    async def enrich(self, product: ProductStub) -> ProductDetailResult:
        decision = await self.policy_check(product.source_url)
        if not decision.allowed:
            raise SourceAccessError(RunStatus.POLICY_DENIED, "detail_policy_denied")
        response = await self.request(product.source_url, "detail")
        raw_html = response.text
        canonical_url = str(response.url)
        fetched_at = datetime.now(UTC)
        parsed = parse_product_detail(raw_html, canonical_url)
        document = FetchedDocument(
            url=canonical_url,
            fetched_at=fetched_at,
            status_code=response.status_code,
            content_hash=hashlib.sha256(raw_html.encode()).hexdigest(),
            raw_html=raw_html,
            parser_version=DETAIL_PARSER_VERSION,
            coverage=parsed.coverage,
            confidence=parsed.confidence,
        )
        return ProductDetailResult(
            listing_external_id=product.external_id,
            canonical_url=canonical_url,
            title=parsed.title,
            brand=parsed.brand,
            seller=MARKETPLACE_LABEL,
            description=parsed.description,
            attributes=parsed.attributes,
            origin=None,
            overseas_sale=None,
            stock=parsed.availability,
            review_url=None,
            coverage=parsed.coverage,
            confidence=parsed.confidence,
            reason_codes=parsed.reason_codes,
            detail_document=document,
            reviews=(),
            review_document=None,
            price=parsed.price,
            old_price=None,
            rating=parsed.rating,
            review_count=parsed.review_count,
            image_url=parsed.image_url,
            seller_count=1,
            offers=parsed.offers,
        )
