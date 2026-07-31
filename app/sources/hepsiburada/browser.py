import asyncio
import hashlib
import json
import random
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import TracebackType
from typing import Any, Self, cast

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.config import Settings
from app.domain.crawl import (
    CrawlLimits,
    FetchedDocument,
    ListingResult,
    PolicyDecision,
    PolicyState,
    ProductDetailResult,
    ProductStub,
    ReviewStub,
    RunStatus,
    SourceAccessError,
)
from app.sources.hepsiburada.detail_parser import (
    RenderedProductDetail,
    RenderedReview,
    build_review_evidence,
    parse_product_detail,
    parse_reviews,
)
from app.sources.hepsiburada.parser import (
    RenderedCategoryLink,
    RenderedProductCard,
    parse_cards,
    parse_category_links,
)
from app.sources.hepsiburada.policy import RobotsPolicy

BASE_URL = "https://www.hepsiburada.com"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
PARSER_VERSION = "hepsiburada-listing-browser-v1"
DETAIL_PARSER_VERSION = "hepsiburada-detail-browser-v1"
REVIEW_PARSER_VERSION = "hepsiburada-review-browser-v1"
USER_AGENT = "PazarRadar/1.4 (+https://github.com/ozcanr17/firsat_radar)"
DAILY_REQUEST_LIMIT = 800
PRODUCT_CARD_SELECTOR = "main article"
PRODUCT_LINK_SELECTOR = "a[href*='-p-'], a[href*='-pm-']"


class HepsiburadaBrowserAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.policy = RobotsPolicy(
            settings.data_dir / "policy",
            settings.robots_cache_hours,
        )
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.rate_limiter = DomainRateLimiter(
            settings.data_dir / "policy" / "hepsiburada-last-request.txt",
            settings.crawl_jitter_min_seconds,
            settings.crawl_jitter_max_seconds,
        )
        self.daily_quota = DailyRequestQuota(
            settings.data_dir / "policy" / "hepsiburada-daily-quota.json"
        )

    async def __aenter__(self) -> Self:
        self.settings.ensure_data_directories()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.context is not None:
            await self.context.close()
        if self.playwright is not None:
            await self.playwright.stop()

    async def policy_check(self, url: str) -> PolicyDecision:
        cached = self.policy.load()
        if cached is not None:
            return self.policy.decide(cached, url, from_cache=True)
        page = await self._active_page()
        await self.rate_limiter.wait()
        self.daily_quota.consume()
        try:
            response = await page.goto(ROBOTS_URL, wait_until="domcontentloaded")
        except PlaywrightTimeoutError as error:
            self.rate_limiter.mark()
            raise SourceAccessError(RunStatus.POLICY_UNAVAILABLE, "robots_timeout") from error
        self.rate_limiter.mark()
        status_code = response.status if response is not None else None
        content = await page.locator("body").inner_text()
        checked_at = datetime.now(UTC)
        cached = self.policy.save(checked_at, status_code, content)
        if self._is_security_block(status_code, await page.title(), content):
            return PolicyDecision(
                state=PolicyState.BLOCKED,
                url=url,
                checked_at=checked_at,
                status_code=status_code,
                content=content,
                content_hash=cached.content_hash,
                cached=False,
                reason_code="robots_security_block",
            )
        return self.policy.decide(cached, url, from_cache=False)

    async def discover(self, start_url: str, limits: CrawlLimits) -> ListingResult:
        limits.validate()
        await self.rate_limiter.wait()
        self.daily_quota.consume()
        page = await self._active_page()
        try:
            response = await page.goto(start_url, wait_until="domcontentloaded")
            await page.wait_for_selector(
                (f"{PRODUCT_CARD_SELECTOR} {PRODUCT_LINK_SELECTOR}, main a[href*='-c-']"),
                state="attached",
                timeout=self.settings.browser_navigation_timeout_seconds * 1000,
            )
        except PlaywrightTimeoutError as error:
            self.rate_limiter.mark()
            raise SourceAccessError(RunStatus.BLOCKED, "listing_timeout_or_blocked") from error
        self.rate_limiter.mark()
        status_code = response.status if response is not None else None
        page_title = await page.title()
        visible_text = await page.locator("body").inner_text(timeout=5000)
        if self._is_security_block(status_code, page_title, visible_text[:3000]):
            raise SourceAccessError(RunStatus.BLOCKED, "listing_security_block")
        raw_cards = await page.locator(PRODUCT_CARD_SELECTOR).evaluate_all(
            """
            articles => articles.map(article => {
                const link = article.querySelector("a[href*='-p-'], a[href*='-pm-']");
                const heading = article.querySelector("h2");
                const image = article.querySelector("img");
                if (!link || !heading) return null;
                const accessibleText = [
                    link.getAttribute("aria-label") || "",
                    heading.getAttribute("aria-label") || ""
                ].join(" ");
                const lines = (article.innerText || "").split("\\n").map(value => value.trim());
                const deliveryText = lines.find(value => /kargoda|teslimat/i.test(value)) || null;
                return {
                    href: link.href,
                    title: heading.innerText || link.textContent || "",
                    accessibleText,
                    visibleText: article.innerText || "",
                    imageUrl: image ? (image.currentSrc || image.src || null) : null,
                    deliveryText
                };
            }).filter(Boolean)
            """
        )
        card_payloads = cast(list[dict[str, Any]], raw_cards)
        cards = [
            RenderedProductCard(
                href=str(card["href"]),
                title=str(card["title"]),
                accessible_text=str(card["accessibleText"]),
                visible_text=str(card["visibleText"]),
                image_url=str(card["imageUrl"]) if card.get("imageUrl") else None,
                delivery_text=str(card["deliveryText"]) if card.get("deliveryText") else None,
            )
            for card in card_payloads
        ]
        raw_category_links = await page.locator("main a[href*='-c-']").evaluate_all(
            """
            links => links.map(link => ({
                href: link.href,
                label: link.innerText || link.getAttribute("aria-label") || ""
            }))
            """
        )
        category_links = parse_category_links(
            [
                RenderedCategoryLink(href=str(link["href"]), label=str(link["label"]))
                for link in cast(list[dict[str, Any]], raw_category_links)
            ],
            BASE_URL,
            page.url,
            self.settings.category_discovery_links_per_page,
        )
        if cards:
            products, coverage = parse_cards(cards, BASE_URL, limits.products)
        elif category_links:
            products, coverage = (), 1.0
        else:
            products, coverage = parse_cards(cards, BASE_URL, limits.products)
        raw_html = await page.content()
        return ListingResult(
            url=page.url,
            fetched_at=datetime.now(UTC),
            status_code=status_code,
            content_hash=hashlib.sha256(raw_html.encode()).hexdigest(),
            raw_html=raw_html,
            products=products,
            candidate_count=min(len(cards), limits.products),
            coverage=coverage,
            parser_version=PARSER_VERSION,
            category_links=category_links,
        )

    async def enrich(self, product: ProductStub) -> ProductDetailResult:
        decision = await self.policy_check(product.source_url)
        if not decision.allowed:
            raise SourceAccessError(RunStatus.POLICY_DENIED, "detail_policy_denied")
        page, status_code = await self._navigate(product.source_url, "detail")
        await page.wait_for_selector("main h1", state="attached")
        detail_payload = cast(
            dict[str, Any],
            await page.locator("main").evaluate(
                """
                main => {
                    const visible = element => element && element.innerText.trim();
                    const heading = main.querySelector("h1");
                    const brandLink = heading ? heading.querySelector("a") : null;
                    const sellerLink = main.querySelector("a[href*='/magaza/']");
                    const reviewLink = main.querySelector("a[href$='-yorumlari']");
                    const panel = main.querySelector("[role='tabpanel']");
                    const panelText = visible(panel) || "";
                    const marker = panelText.indexOf("Ürün özellikleri");
                    const description = marker >= 0 ? panelText.slice(0, marker) : panelText;
                    const documents = Array.from(document.querySelectorAll(
                        "script[type='application/ld+json']"
                    )).flatMap(node => {
                        try {
                            const value = JSON.parse(node.textContent || "null");
                            if (!value) return [];
                            if (Array.isArray(value)) return value;
                            return value["@graph"] || [value];
                        } catch {
                            return [];
                        }
                    });
                    const product = documents.find(value => {
                        const type = value && value["@type"];
                        return type === "Product" || (
                            Array.isArray(type) && type.includes("Product")
                        );
                    }) || {};
                    const offers = Array.isArray(product.offers)
                        ? product.offers[0]
                        : product.offers || {};
                    const rating = product.aggregateRating || {};
                    const images = Array.isArray(product.image) ? product.image : [product.image];
                    return {
                        title: visible(heading) || "",
                        brand: visible(brandLink) || null,
                        seller: visible(sellerLink) || null,
                        reviewUrl: reviewLink ? reviewLink.href : null,
                        description,
                        productInfoText: panelText,
                        price: offers.price || offers.lowPrice || null,
                        oldPrice: offers.highPrice || null,
                        rating: rating.ratingValue || null,
                        reviewCount: rating.reviewCount || rating.ratingCount || null,
                        imageUrl: images.find(Boolean) || null
                    };
                }
                """
            ),
        )
        canonical_url = page.url
        detail_raw_html = await page.content()
        fetched_at = datetime.now(UTC)
        parsed = parse_product_detail(
            RenderedProductDetail(
                title=str(detail_payload["title"]),
                brand=str(detail_payload["brand"]) if detail_payload.get("brand") else None,
                seller=str(detail_payload["seller"]) if detail_payload.get("seller") else None,
                description=str(detail_payload["description"])
                if detail_payload.get("description")
                else None,
                product_info_text=str(detail_payload["productInfoText"]),
                review_url=str(detail_payload["reviewUrl"])
                if detail_payload.get("reviewUrl")
                else None,
            )
        )
        detail_document = FetchedDocument(
            url=canonical_url,
            fetched_at=fetched_at,
            status_code=status_code,
            content_hash=hashlib.sha256(detail_raw_html.encode()).hexdigest(),
            raw_html=detail_raw_html,
            parser_version=DETAIL_PARSER_VERSION,
            coverage=parsed.coverage,
            confidence=parsed.confidence,
        )
        reviews: tuple[ReviewStub, ...] = ()
        review_document: FetchedDocument | None = None
        reason_codes = list(parsed.reason_codes)
        reviews, review_document = await self._collect_visible_reviews(
            page,
            canonical_url,
            status_code,
        )
        if not reviews:
            reason_codes.append("visible_reviews_unavailable")
        return ProductDetailResult(
            listing_external_id=product.external_id,
            canonical_url=canonical_url,
            title=parsed.title,
            brand=parsed.brand,
            seller=parsed.seller,
            description=parsed.description,
            attributes=parsed.attributes,
            origin=parsed.origin,
            overseas_sale=parsed.overseas_sale,
            stock=parsed.stock,
            review_url=parsed.review_url,
            coverage=parsed.coverage,
            confidence=parsed.confidence,
            reason_codes=tuple(reason_codes),
            detail_document=detail_document,
            reviews=reviews,
            review_document=review_document,
            price=parse_optional_decimal(detail_payload.get("price")),
            old_price=parse_optional_decimal(detail_payload.get("oldPrice")),
            rating=parse_optional_float(detail_payload.get("rating")),
            review_count=parse_optional_int(detail_payload.get("reviewCount")),
            image_url=str(detail_payload["imageUrl"]) if detail_payload.get("imageUrl") else None,
        )

    async def _collect_visible_reviews(
        self,
        page: Page,
        canonical_url: str,
        status_code: int | None,
    ) -> tuple[tuple[ReviewStub, ...], FetchedDocument]:
        projected = cast(
            list[dict[str, Any]],
            await page.locator("main").evaluate(
                """
                main => {
                    const nodes = Array.from(main.querySelectorAll("article, li, div"));
                    const containsReview = element => {
                        const text = element.innerText || "";
                        return text.includes("Kullanıcı bu ürünü") &&
                            text.includes("Bu değerlendirme faydalı mı?");
                    };
                    return nodes.filter(element => containsReview(element) &&
                        !Array.from(element.children).some(containsReview))
                        .slice(0, 20)
                        .map(element => {
                            const lines = (element.innerText || "").split("\\n")
                                .map(value => value.trim()).filter(Boolean);
                            const dateText = lines.find(value =>
                                /^\\d{1,2}\\s+[A-Za-zÇĞİÖŞÜçğıöşü]+/.test(value)) || null;
                            const identityIndex = lines.findIndex(value => /\\*{3}/.test(value));
                            const markerIndex = lines.findIndex(value =>
                                value === "Kullanıcı bu ürünü");
                            const start = identityIndex >= 0 ? identityIndex + 1 : 0;
                            const end = markerIndex > start ? markerIndex : lines.length;
                            return {dateText, text: lines.slice(start, end).join(" ")};
                        }).filter(review => review.text);
                }
                """
            ),
        )
        observed_at = datetime.now(UTC)
        reviews = parse_reviews(
            [
                RenderedReview(
                    date_text=str(item["dateText"]) if item.get("dateText") else None,
                    text=str(item["text"]),
                )
                for item in projected
            ],
            canonical_url,
            canonical_url,
            observed_at,
        )
        evidence = build_review_evidence(reviews)
        coverage = 1.0 if reviews else 0.0
        document = FetchedDocument(
            url=canonical_url,
            fetched_at=observed_at,
            status_code=status_code,
            content_hash=hashlib.sha256(evidence.encode()).hexdigest(),
            raw_html=evidence,
            parser_version=REVIEW_PARSER_VERSION,
            coverage=coverage,
            confidence=coverage,
        )
        return reviews, document

    async def _navigate(self, url: str, page_kind: str) -> tuple[Page, int | None]:
        await self.rate_limiter.wait()
        self.daily_quota.consume()
        page = await self._active_page()
        try:
            response = await page.goto(url, wait_until="domcontentloaded")
        except PlaywrightTimeoutError as error:
            self.rate_limiter.mark()
            raise SourceAccessError(RunStatus.BLOCKED, f"{page_kind}_timeout") from error
        self.rate_limiter.mark()
        status_code = response.status if response is not None else None
        page_title = await page.title()
        visible_text = await page.locator("body").inner_text(timeout=5000)
        if self._is_security_block(status_code, page_title, visible_text[:3000]):
            raise SourceAccessError(RunStatus.BLOCKED, f"{page_kind}_security_block")
        return page, status_code

    async def _active_page(self) -> Page:
        if self.page is not None:
            return self.page
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.settings.data_dir / "browser",
            channel=self.settings.browser_channel or None,
            headless=self.settings.browser_headless,
            locale="tr-TR",
            timezone_id=self.settings.timezone,
            user_agent=USER_AGENT,
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        self.page.set_default_navigation_timeout(
            self.settings.browser_navigation_timeout_seconds * 1000
        )
        return self.page

    @staticmethod
    def _is_security_block(status_code: int | None, title: str, content: str) -> bool:
        if status_code in {403, 429}:
            return True
        signal = f"{title} {content}".casefold()
        return any(
            marker in signal
            for marker in (
                "hepsiburada | güvenlik",
                "hbblockandcaptcha",
                "access denied",
                "captcha",
            )
        )


class DomainRateLimiter:
    def __init__(self, state_path: Path, minimum_seconds: float, maximum_seconds: float) -> None:
        self.state_path = state_path
        self.minimum_seconds = minimum_seconds
        self.maximum_seconds = maximum_seconds

    async def wait(self) -> None:
        if not self.state_path.exists():
            return
        try:
            last_request_at = datetime.fromisoformat(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        interval = random.uniform(self.minimum_seconds, self.maximum_seconds)
        elapsed = (datetime.now(UTC) - last_request_at).total_seconds()
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)

    def mark(self) -> None:
        self.state_path.write_text(datetime.now(UTC).isoformat(), encoding="utf-8")


class DailyRequestQuota:
    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path

    def consume(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        count = 0
        if self.state_path.exists():
            try:
                payload = json.loads(self.state_path.read_text(encoding="utf-8"))
                if payload.get("date") == today:
                    count = int(payload.get("count", 0))
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                count = 0
        if count >= DAILY_REQUEST_LIMIT:
            raise SourceAccessError(RunStatus.FAILED, "daily_quota_reached")
        self.state_path.write_text(
            json.dumps({"date": today, "count": count + 1}),
            encoding="utf-8",
        )


def parse_optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        return None
    return result if result >= 0 else None


def parse_optional_float(value: object) -> float | None:
    try:
        result = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return result if 0 <= result <= 5 else None


def parse_optional_int(value: object) -> int | None:
    try:
        result = int(str(value).replace(".", ""))
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None
