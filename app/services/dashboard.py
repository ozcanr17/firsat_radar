from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

from app.db.models import CrawlRun, Opportunity, Product, Review
from app.db.session import SessionFactory


@dataclass(frozen=True)
class DashboardStats:
    product_count: int
    review_count: int
    opportunity_count: int
    run_count: int
    last_run_at: datetime | None
    last_run_status: str | None


def get_dashboard_stats(session_factory: SessionFactory) -> DashboardStats:
    with session_factory() as session:
        product_count = session.scalar(select(func.count()).select_from(Product)) or 0
        review_count = session.scalar(select(func.count()).select_from(Review)) or 0
        opportunity_count = (
            session.scalar(select(func.count(func.distinct(Opportunity.product_id)))) or 0
        )
        run_count = session.scalar(select(func.count()).select_from(CrawlRun)) or 0
        latest_run = session.scalar(
            select(CrawlRun).order_by(CrawlRun.started_at.desc(), CrawlRun.id.desc()).limit(1)
        )
    return DashboardStats(
        product_count=product_count,
        review_count=review_count,
        opportunity_count=opportunity_count,
        run_count=run_count,
        last_run_at=latest_run.started_at if latest_run else None,
        last_run_status=latest_run.status if latest_run else None,
    )
