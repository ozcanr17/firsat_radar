import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import Settings


@dataclass(frozen=True)
class BackupResult:
    path: Path
    size_bytes: int
    integrity: str
    backups_removed: int


class DatabaseBackupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.directory = settings.data_dir / "backups"
        self.directory.mkdir(parents=True, exist_ok=True)

    def create(self, now: datetime | None = None) -> BackupResult:
        url = make_url(self.settings.resolved_database_url)
        if url.get_backend_name() != "sqlite" or not url.database:
            raise ValueError("Only file-based SQLite backups are supported")
        source_path = Path(url.database).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        active_now = now or datetime.now(UTC)
        timestamp = active_now.strftime("%Y%m%dT%H%M%S%fZ")
        destination = self.directory / f"firsat-radar-{timestamp}.db"
        source_uri = f"file:{source_path.as_posix()}?mode=ro"
        with (
            sqlite3.connect(source_uri, uri=True) as source,
            sqlite3.connect(destination) as target,
        ):
            source.backup(target)
            integrity_row = target.execute("PRAGMA integrity_check").fetchone()
        integrity = str(integrity_row[0]) if integrity_row else "unavailable"
        if integrity != "ok":
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"Backup integrity check failed: {integrity}")
        removed = self._prune()
        return BackupResult(
            path=destination,
            size_bytes=destination.stat().st_size,
            integrity=integrity,
            backups_removed=removed,
        )

    def _prune(self) -> int:
        backups = sorted(
            self.directory.glob("firsat-radar-*.db"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        removed = 0
        for path in backups[self.settings.backup_retention_count :]:
            if path.is_file():
                path.unlink()
                removed += 1
        return removed
