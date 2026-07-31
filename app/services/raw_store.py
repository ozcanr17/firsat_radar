import gzip
from datetime import datetime
from pathlib import Path


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
