import asyncio
import hashlib
import random
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self, cast

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.config import Settings
from app.domain.crawl import (
    CrawlLimits,
    ListingResult,
    PolicyDecision,
    PolicyState,
    RunStatus,
    SourceAccessError,
)
from app.sources.hepsiburada.parser import RenderedProductCard, parse_cards
from app.sources.hepsiburada.policy import RobotsPolicy

BASE_URL = "https://www.hepsiburada.com"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
PARSER_VERSION = "hepsiburada-listing-browser-v1"
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
        page = await self._active_page()
        try:
            response = await page.goto(start_url, wait_until="domcontentloaded")
            await page.wait_for_selector(
                f"{PRODUCT_CARD_SELECTOR} {PRODUCT_LINK_SELECTOR}",
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
        )

    async def _active_page(self) -> Page:
        if self.page is not None:
            return self.page
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.settings.data_dir / "browser",
            channel=self.settings.browser_channel,
            headless=self.settings.browser_headless,
            locale="tr-TR",
            timezone_id=self.settings.timezone,
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
