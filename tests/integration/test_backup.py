import sqlite3
from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.db.migrations import upgrade_database
from app.services.backup import DatabaseBackupService


def test_sqlite_backup_integrity_and_retention(settings: Settings) -> None:
    settings = Settings(
        environment="test",
        data_dir=settings.data_dir,
        backup_retention_count=2,
    )
    upgrade_database(settings)
    service = DatabaseBackupService(settings)
    now = datetime(2026, 7, 31, tzinfo=UTC)

    first = service.create(now)
    second = service.create(now + timedelta(seconds=1))
    third = service.create(now + timedelta(seconds=2))

    backups = list((settings.data_dir / "backups").glob("firsat-radar-*.db"))
    with sqlite3.connect(third.path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert first.integrity == "ok"
    assert second.integrity == "ok"
    assert third.integrity == "ok"
    assert third.backups_removed == 1
    assert len(backups) == 2
    assert first.path.exists() is False
    assert "products" in tables
    assert "runtime_state" in tables
