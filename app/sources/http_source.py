from datetime import UTC, datetime
from types import TracebackType
from typing import Self

import httpx

from app.config import Settings
from app.domain.crawl import PolicyDecision, RunStatus, SourceAccessError
from app.sources.robots import RobotsPolicy
from app.sources.throttle import DailyRequestQuota, DomainRateLimiter, RateLimitCooldown

ACCEPT_HEADER = "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8"
CHALLENGE_MARKERS = ("just a moment", "access denied", "attention required", "captcha")


class HttpSourceAdapter:
    def __init__(
        self,
        settings: Settings,
        *,
        base_url: str,
        cache_prefix: str,
        user_agent: str,
        crawler_token: str,
        min_request_seconds: float,
        max_request_seconds: float,
        cooldown_minutes: int,
        daily_request_limit: int,
        block_markers: tuple[str, ...] = CHALLENGE_MARKERS,
    ) -> None:
        self.settings = settings
        self.base_url = base_url
        self.robots_url = f"{base_url}/robots.txt"
        self.user_agent = user_agent
        self.block_markers = block_markers
        policy_directory = settings.data_dir / "policy"
        self.policy = RobotsPolicy(
            policy_directory,
            settings.robots_cache_hours,
            robots_url=self.robots_url,
            user_agent=crawler_token,
            cache_name=f"{cache_prefix}-robots.json",
            block_markers=block_markers,
        )
        self.rate_limiter = DomainRateLimiter(
            policy_directory / f"{cache_prefix}-last-request.txt",
            min_request_seconds,
            max_request_seconds,
        )
        self.daily_quota = DailyRequestQuota(
            policy_directory / f"{cache_prefix}-daily-quota.json",
            daily_request_limit,
        )
        self.cooldown = RateLimitCooldown(
            policy_directory / f"{cache_prefix}-cooldown.txt",
            cooldown_minutes,
        )
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self.settings.ensure_data_directories()
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": self.user_agent,
                "Accept": ACCEPT_HEADER,
                "Accept-Language": "tr-TR,tr;q=0.9",
            },
            timeout=httpx.Timeout(self.settings.browser_navigation_timeout_seconds),
            follow_redirects=True,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def policy_check(self, url: str) -> PolicyDecision:
        cached = self.policy.load()
        if cached is not None:
            return self.policy.decide(cached, url, from_cache=True)
        response = await self.request(self.robots_url, "robots")
        cached = self.policy.save(datetime.now(UTC), response.status_code, response.text)
        return self.policy.decide(cached, url, from_cache=False)

    async def request(self, url: str, page_kind: str) -> httpx.Response:
        if self.client is None:
            raise SourceAccessError(RunStatus.FAILED, f"{page_kind}_client_unavailable")
        if self.cooldown.active_until() is not None:
            raise SourceAccessError(RunStatus.FAILED, f"{page_kind}_rate_limit_cooldown")
        await self.rate_limiter.wait()
        self.daily_quota.consume()
        try:
            response = await self.client.get(url)
        except httpx.HTTPError as error:
            self.rate_limiter.mark()
            raise SourceAccessError(RunStatus.BLOCKED, f"{page_kind}_request_failed") from error
        self.rate_limiter.mark()
        if response.status_code == 429:
            self.cooldown.engage(parse_retry_after(response.headers.get("retry-after")))
            raise SourceAccessError(RunStatus.FAILED, f"{page_kind}_rate_limited")
        if response.status_code == 403:
            raise SourceAccessError(RunStatus.BLOCKED, f"{page_kind}_access_denied")
        if response.status_code >= 400:
            raise SourceAccessError(RunStatus.FAILED, f"{page_kind}_http_{response.status_code}")
        signal = response.text[:3000].casefold()
        if any(marker in signal for marker in self.block_markers):
            self.cooldown.engage()
            raise SourceAccessError(RunStatus.FAILED, f"{page_kind}_challenge")
        self.cooldown.clear()
        return response


def parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None
