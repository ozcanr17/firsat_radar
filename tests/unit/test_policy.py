from datetime import UTC, datetime
from pathlib import Path

from app.domain.crawl import PolicyState
from app.sources.hepsiburada.policy import RobotsPolicy

ROBOTS = """User-agent: *
Disallow: /api/
Disallow: /product-comment/
"""


def test_public_category_is_allowed(tmp_path: Path) -> None:
    policy = RobotsPolicy(tmp_path, 24)
    cached = policy.save(datetime.now(UTC), 200, ROBOTS)

    decision = policy.decide(
        cached,
        "https://www.hepsiburada.com/anne-bebek-oyuncak-c-2147483639",
        from_cache=False,
    )

    assert decision.state is PolicyState.ALLOWED


def test_restricted_api_is_denied(tmp_path: Path) -> None:
    policy = RobotsPolicy(tmp_path, 24)
    cached = policy.save(datetime.now(UTC), 200, ROBOTS)

    decision = policy.decide(
        cached,
        "https://www.hepsiburada.com/api/products",
        from_cache=False,
    )

    assert decision.state is PolicyState.DENIED


def test_security_block_remains_blocked_when_cached(tmp_path: Path) -> None:
    policy = RobotsPolicy(tmp_path, 24)
    cached = policy.save(datetime.now(UTC), 403, "HBBlockAndCaptcha")

    decision = policy.decide(
        cached,
        "https://www.hepsiburada.com/anne-bebek-oyuncak-c-2147483639",
        from_cache=True,
    )

    assert decision.state is PolicyState.BLOCKED
    assert decision.reason_code == "robots_security_block"
