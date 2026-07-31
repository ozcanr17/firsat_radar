import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.raw_store import RawStore


def test_raw_retention_supports_dry_run_and_bounded_delete(tmp_path: Path) -> None:
    store = RawStore(tmp_path / "raw")
    now = datetime(2026, 7, 31, tzinfo=UTC)
    old_path = store.save("old", "a" * 64, now - timedelta(days=10), "html")
    recent_path = store.save("recent", "b" * 64, now, "html")
    old_timestamp = (now - timedelta(days=10)).timestamp()
    recent_timestamp = now.timestamp()
    os.utime(old_path, (old_timestamp, old_timestamp))
    os.utime(recent_path, (recent_timestamp, recent_timestamp))

    preview = store.prune(7, now=now, dry_run=True)
    applied = store.prune(7, now=now, dry_run=False)

    assert preview.scanned == 2
    assert preview.eligible == 1
    assert preview.deleted == 0
    assert old_path.exists() is False
    assert recent_path.exists() is True
    assert applied.deleted == 1
    assert applied.bytes_deleted > 0
