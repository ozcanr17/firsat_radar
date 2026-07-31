from datetime import UTC, datetime

import pytest

from app.config import Settings
from app.db.session import SessionFactory
from app.domain.crawl import CrawlSummary, RunStatus
from app.services.collection import MultiSourceCollector, SourceCollection, empty_summary
from app.services.source_state import SourceStateService


class StubBatch:
    def __init__(self, summary: CrawlSummary | None = None, error: Exception | None = None) -> None:
        self.summary = summary
        self.error = error
        self.calls = 0

    async def run_batch(self, page_count: int) -> CrawlSummary:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.summary is not None
        return self.summary


def completed_summary(products: int = 5) -> CrawlSummary:
    return CrawlSummary(
        run_id=1,
        status=RunStatus.COMPLETED,
        products_seen=products,
        products_created=products,
        products_updated=0,
        snapshots_created=products,
        details_created=0,
        reviews_created=0,
        fetches_created=1,
        error_code=None,
        listing_signature="abc",
    )


def blocked_summary() -> CrawlSummary:
    return CrawlSummary(
        run_id=2,
        status=RunStatus.BLOCKED,
        products_seen=0,
        products_created=0,
        products_updated=0,
        snapshots_created=0,
        details_created=0,
        reviews_created=0,
        fetches_created=1,
        error_code="listing_security_block",
        listing_signature=None,
    )


def build_collector(
    session_factory: SessionFactory,
    collections: tuple[SourceCollection, ...],
) -> tuple[MultiSourceCollector, SourceStateService]:
    settings = Settings(environment="test", catalog_enabled=True, watchlist_enabled=False)
    state = SourceStateService(session_factory)
    return MultiSourceCollector(settings, state, collections), state


@pytest.mark.asyncio
async def test_blocked_source_does_not_stop_healthy_source(
    session_factory: SessionFactory,
) -> None:
    blocked = StubBatch(blocked_summary())
    healthy = StubBatch(completed_summary())
    collector, state = build_collector(
        session_factory,
        (
            SourceCollection(source_name="hepsiburada", catalog=blocked),
            SourceCollection(source_name="vatan", catalog=healthy),
        ),
    )

    summary = await collector.run_batch(1)

    assert healthy.calls == 1
    assert summary.status is RunStatus.COMPLETED
    assert summary.products_seen == 5
    assert state.get("hepsiburada").circuit_is_open()
    assert state.get("hepsiburada").last_error_code == "listing_security_block"
    assert not state.get("vatan").circuit_is_open()
    assert state.get("vatan").status == "completed"


@pytest.mark.asyncio
async def test_open_circuit_skips_only_its_own_source(session_factory: SessionFactory) -> None:
    blocked = StubBatch(blocked_summary())
    healthy = StubBatch(completed_summary())
    collector, _state = build_collector(
        session_factory,
        (
            SourceCollection(source_name="hepsiburada", catalog=blocked),
            SourceCollection(source_name="vatan", catalog=healthy),
        ),
    )

    await collector.run_batch(1)
    await collector.run_batch(1)

    assert blocked.calls == 1
    assert healthy.calls == 2
    outcomes = {item.source_name: item.status for item in collector.last_outcomes}
    assert outcomes["hepsiburada"] == "circuit_open"
    assert outcomes["vatan"] == "completed"


@pytest.mark.asyncio
async def test_rate_limited_source_is_throttled_not_circuit_opened(
    session_factory: SessionFactory,
) -> None:
    throttled = CrawlSummary(
        run_id=3,
        status=RunStatus.FAILED,
        products_seen=0,
        products_created=0,
        products_updated=0,
        snapshots_created=0,
        details_created=0,
        reviews_created=0,
        fetches_created=0,
        error_code="listing_rate_limited",
        listing_signature=None,
    )
    collector, state = build_collector(
        session_factory,
        (SourceCollection(source_name="akakce", catalog=StubBatch(throttled)),),
    )

    await collector.run_batch(1)

    snapshot = state.get("akakce")
    assert snapshot.status == "throttled"
    assert snapshot.consecutive_failures == 0
    assert not snapshot.circuit_is_open()


@pytest.mark.asyncio
async def test_source_exception_is_isolated(session_factory: SessionFactory) -> None:
    healthy = StubBatch(completed_summary(3))
    collector, state = build_collector(
        session_factory,
        (
            SourceCollection(source_name="akakce", catalog=StubBatch(error=RuntimeError("boom"))),
            SourceCollection(source_name="vatan", catalog=healthy),
        ),
    )

    summary = await collector.run_batch(1)

    assert healthy.calls == 1
    assert summary.status is RunStatus.COMPLETED
    assert state.get("akakce").last_error_code == "runtimeerror"
    assert state.get("vatan").status == "completed"


@pytest.mark.asyncio
async def test_all_sources_skipped_returns_unchanged(session_factory: SessionFactory) -> None:
    collector, state = build_collector(
        session_factory,
        (SourceCollection(source_name="akakce", catalog=StubBatch(blocked_summary())),),
    )
    state.mark_failure(
        "akakce",
        datetime.now(UTC),
        "listing_security_block",
        threshold=1,
        cooldown_hours=24,
        force_open=True,
    )

    summary = await collector.run_batch(1)

    assert summary.status is RunStatus.UNCHANGED
    assert summary == empty_summary()
