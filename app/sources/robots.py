import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.robotparser import RobotFileParser

from app.domain.crawl import PolicyDecision, PolicyState

DEFAULT_BLOCK_MARKERS = ("access denied", "captcha", "attention required")


@dataclass(frozen=True)
class CachedPolicy:
    checked_at: datetime
    status_code: int | None
    content: str
    content_hash: str


class RobotsPolicy:
    def __init__(
        self,
        cache_directory: Path,
        cache_hours: int,
        *,
        robots_url: str,
        user_agent: str,
        cache_name: str,
        block_markers: tuple[str, ...] = DEFAULT_BLOCK_MARKERS,
    ) -> None:
        self.cache_path = cache_directory / cache_name
        self.cache_lifetime = timedelta(hours=cache_hours)
        self.robots_url = robots_url
        self.user_agent = user_agent
        self.block_markers = block_markers

    def load(self) -> CachedPolicy | None:
        if not self.cache_path.exists():
            return None
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            cached = CachedPolicy(
                checked_at=datetime.fromisoformat(payload["checked_at"]),
                status_code=payload["status_code"],
                content=payload["content"],
                content_hash=payload["content_hash"],
            )
        except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
            return None
        if datetime.now(UTC) - cached.checked_at > self.cache_lifetime:
            return None
        return cached

    def save(self, checked_at: datetime, status_code: int | None, content: str) -> CachedPolicy:
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        cached = CachedPolicy(
            checked_at=checked_at,
            status_code=status_code,
            content=content,
            content_hash=content_hash,
        )
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(asdict(cached), default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        return cached

    def decide(self, cached: CachedPolicy, target_url: str, from_cache: bool) -> PolicyDecision:
        signal = cached.content.casefold()
        if cached.status_code in {403, 429} or any(
            marker in signal for marker in self.block_markers
        ):
            return self._decision(
                cached,
                target_url,
                from_cache,
                PolicyState.BLOCKED,
                "robots_security_block",
            )
        if cached.status_code != 200 or not cached.content.strip():
            return self._decision(
                cached,
                target_url,
                from_cache,
                PolicyState.UNAVAILABLE,
                "robots_unavailable",
            )
        parser = RobotFileParser()
        parser.set_url(self.robots_url)
        parser.parse(cached.content.splitlines())
        allowed = parser.can_fetch(self.user_agent, target_url)
        return self._decision(
            cached,
            target_url,
            from_cache,
            PolicyState.ALLOWED if allowed else PolicyState.DENIED,
            None if allowed else "robots_disallow",
        )

    @staticmethod
    def _decision(
        cached: CachedPolicy,
        target_url: str,
        from_cache: bool,
        state: PolicyState,
        reason_code: str | None,
    ) -> PolicyDecision:
        return PolicyDecision(
            state=state,
            url=target_url,
            checked_at=cached.checked_at,
            status_code=cached.status_code,
            content=cached.content,
            content_hash=cached.content_hash,
            cached=from_cache,
            reason_code=reason_code,
        )
