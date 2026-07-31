import gzip
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class PruneResult:
    scanned: int
    eligible: int
    deleted: int
    bytes_deleted: int


class RawStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, content: str, content_hash: str, observed_at: datetime, suffix: str) -> Path:
        timestamp = observed_at.strftime("%Y%m%dT%H%M%SZ")
        path = self.directory / f"{timestamp}-{content_hash[:16]}.{suffix}.gz"
        if not path.exists():
            with gzip.open(path, "wt", encoding="utf-8") as output:
                output.write(content)
        return path

    def prune(
        self,
        retention_days: int,
        now: datetime | None = None,
        dry_run: bool = True,
    ) -> PruneResult:
        if not 1 <= retention_days <= 30:
            raise ValueError("Raw retention must be between 1 and 30 days")
        active_now = now or datetime.now(UTC)
        cutoff = active_now - timedelta(days=retention_days)
        scanned = 0
        eligible = 0
        deleted = 0
        bytes_deleted = 0
        for path in self.directory.glob("*.gz"):
            if not path.is_file():
                continue
            scanned += 1
            stat = path.stat()
            modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            if modified_at >= cutoff:
                continue
            eligible += 1
            if dry_run:
                continue
            path.unlink()
            deleted += 1
            bytes_deleted += stat.st_size
        return PruneResult(
            scanned=scanned,
            eligible=eligible,
            deleted=deleted,
            bytes_deleted=bytes_deleted,
        )
