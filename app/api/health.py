from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import CrawlRun
from app.db.session import SessionFactory


class HealthResponse(BaseModel):
    status: str
    database: str
    last_run_at: datetime | None


def create_health_router(session_factory: SessionFactory) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/healthz",
        response_model=HealthResponse,
        status_code=status.HTTP_200_OK,
    )
    def health() -> HealthResponse:
        try:
            with session_factory() as session:
                last_run_at = session.scalar(
                    select(CrawlRun.started_at).order_by(CrawlRun.started_at.desc()).limit(1)
                )
        except SQLAlchemyError:
            return HealthResponse(status="degraded", database="unavailable", last_run_at=None)
        return HealthResponse(status="ok", database="ok", last_run_at=last_run_at)

    return router
