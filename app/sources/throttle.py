import asyncio
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.crawl import RunStatus, SourceAccessError

DAILY_REQUEST_LIMIT = 800


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


class RateLimitCooldown:
    def __init__(self, state_path: Path, cooldown_minutes: int) -> None:
        self.state_path = state_path
        self.cooldown = timedelta(minutes=cooldown_minutes)

    def active_until(self) -> datetime | None:
        if not self.state_path.exists():
            return None
        try:
            until = datetime.fromisoformat(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return until if until > datetime.now(UTC) else None

    def engage(self, retry_after_seconds: float | None = None) -> datetime:
        delay = (
            timedelta(seconds=retry_after_seconds)
            if retry_after_seconds is not None
            else self.cooldown
        )
        until = datetime.now(UTC) + max(delay, self.cooldown)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(until.isoformat(), encoding="utf-8")
        return until

    def clear(self) -> None:
        self.state_path.unlink(missing_ok=True)


class DailyRequestQuota:
    def __init__(self, state_path: Path, limit: int = DAILY_REQUEST_LIMIT) -> None:
        self.state_path = state_path
        self.limit = limit

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
        if count >= self.limit:
            raise SourceAccessError(RunStatus.FAILED, "daily_quota_reached")
        self.state_path.write_text(
            json.dumps({"date": today, "count": count + 1}),
            encoding="utf-8",
        )
