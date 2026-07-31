from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import CrawlRun
from app.db.session import SessionFactory
from app.services.runtime_state import RuntimeStateService


class HealthResponse(BaseModel):
    status: str
    database: str
    last_run_at: datetime | None
    scheduler_status: str
    consecutive_failures: int
    circuit_open_until: datetime | None
    last_backup_at: datetime | None


def create_health_router(session_factory: SessionFactory) -> APIRouter:
    router = APIRouter()
    runtime_service = RuntimeStateService(session_factory)

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
            runtime = runtime_service.get()
        except SQLAlchemyError:
            return HealthResponse(
                status="degraded",
                database="unavailable",
                last_run_at=None,
                scheduler_status="unknown",
                consecutive_failures=0,
                circuit_open_until=None,
                last_backup_at=None,
            )
        return HealthResponse(
            status="ok",
            database="ok",
            last_run_at=last_run_at,
            scheduler_status=runtime.scheduler_status,
            consecutive_failures=runtime.consecutive_failures,
            circuit_open_until=runtime.circuit_open_until,
            last_backup_at=runtime.last_backup_at,
        )

    return router
