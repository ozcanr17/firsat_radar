from types import TracebackType
from typing import Protocol, Self

from app.domain.crawl import (
    CrawlLimits,
    ListingResult,
    PolicyDecision,
    ProductDetailResult,
    ProductStub,
)


class SourceAdapter(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def policy_check(self, url: str) -> PolicyDecision: ...

    async def discover(self, start_url: str, limits: CrawlLimits) -> ListingResult: ...

    async def enrich(self, product: ProductStub) -> ProductDetailResult: ...
