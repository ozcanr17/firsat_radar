import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.db.models import CrawlRun, Source
from app.db.session import SessionFactory


@dataclass(frozen=True)
class RunView:
    id: int
    source: str
    started_at: datetime
    ended_at: datetime | None
    status: str
    products_seen: int
    details_created: int
    reviews_created: int
    fetches_created: int
    error_code: str | None


def list_runs(session_factory: SessionFactory, limit: int = 50) -> list[RunView]:
    with session_factory() as session:
        rows = session.execute(
            select(CrawlRun, Source)
            .join(Source, Source.id == CrawlRun.source_id)
            .order_by(CrawlRun.started_at.desc(), CrawlRun.id.desc())
            .limit(limit)
        ).all()
    result = []
    for run, source in rows:
        counts = json.loads(run.counts_json)
        result.append(
            RunView(
                id=run.id,
                source=source.name,
                started_at=run.started_at,
                ended_at=run.ended_at,
                status=run.status,
                products_seen=int(counts.get("products_seen", 0)),
                details_created=int(counts.get("details_created", 0)),
                reviews_created=int(counts.get("reviews_created", 0)),
                fetches_created=int(counts.get("fetches_created", 0)),
                error_code=run.error_code,
            )
        )
    return result
