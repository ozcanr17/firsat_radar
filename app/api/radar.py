from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from app.config import Settings
from app.db.session import SessionFactory
from app.services.catalog import CatalogMonitor
from app.services.commerce import list_watch_targets
from app.services.dashboard import get_dashboard_stats
from app.services.runtime_state import RuntimeStateService


class RadarStatusResponse(BaseModel):
    scheduler_enabled: bool
    catalog_enabled: bool
    scheduler_interval_hours: int
    scheduler_status: str
    last_started_at: datetime | None
    last_finished_at: datetime | None
    last_error_code: str | None
    circuit_open_until: datetime | None
    product_count: int
    review_count: int
    opportunity_count: int
    run_count: int
    watch_target_count: int
    due_target_count: int
    category_count: int
    enabled_category_count: int
    pages_scanned: int
    next_category: str | None
    next_page: int | None


class RadarRunResponse(BaseModel):
    status: str
    message: str


class CategoryStateRequest(BaseModel):
    enabled: bool


class CategoryResponse(BaseModel):
    id: int
    name: str
    url: str
    enabled: bool
    priority: int
    next_page: int
    pages_scanned: int
    sweeps_completed: int
    last_status: str
    last_crawled_at: datetime | None


def create_radar_router(settings: Settings, session_factory: SessionFactory) -> APIRouter:
    router = APIRouter(prefix="/api/v1/radar")

    def catalog() -> CatalogMonitor:
        return CatalogMonitor(
            session_factory,
            None,
            settings.catalog_products_per_page,
            settings.catalog_details_per_page,
        )

    @router.get("", response_model=RadarStatusResponse)
    def status() -> RadarStatusResponse:
        runtime = RuntimeStateService(session_factory).get()
        stats = get_dashboard_stats(session_factory)
        targets = list_watch_targets(session_factory)
        catalog_status = catalog().status()
        return RadarStatusResponse(
            scheduler_enabled=settings.embedded_scheduler_enabled,
            catalog_enabled=settings.catalog_enabled,
            scheduler_interval_hours=settings.scheduler_interval_hours,
            scheduler_status=runtime.scheduler_status,
            last_started_at=runtime.last_job_started_at,
            last_finished_at=runtime.last_job_finished_at,
            last_error_code=runtime.last_error_code,
            circuit_open_until=runtime.circuit_open_until,
            product_count=stats.product_count,
            review_count=stats.review_count,
            opportunity_count=stats.opportunity_count,
            run_count=stats.run_count,
            watch_target_count=len(targets),
            due_target_count=sum(target.refresh_due for target in targets),
            category_count=catalog_status.category_count,
            enabled_category_count=catalog_status.enabled_count,
            pages_scanned=catalog_status.pages_scanned,
            next_category=catalog_status.next_category,
            next_page=catalog_status.next_page,
        )

    @router.post("/run", response_model=RadarRunResponse, status_code=202)
    def run_now(
        request: Request,
        background_tasks: BackgroundTasks,
    ) -> RadarRunResponse:
        runtime = RuntimeStateService(session_factory).get()
        if runtime.scheduler_status == "running":
            raise HTTPException(status_code=409, detail="radar_already_running")
        background_tasks.add_task(request.app.state.pipeline.run)
        return RadarRunResponse(
            status="queued",
            message="Keşif, ürün yenileme ve analiz çalışması sıraya alındı.",
        )

    @router.get("/categories", response_model=list[CategoryResponse])
    def categories() -> list[CategoryResponse]:
        return [
            CategoryResponse.model_validate(item, from_attributes=True)
            for item in catalog().categories()
        ]

    @router.patch("/categories/{category_id}", response_model=CategoryResponse)
    def update_category(
        category_id: int,
        payload: CategoryStateRequest,
    ) -> CategoryResponse:
        category = catalog().set_enabled(category_id, payload.enabled)
        if category is None:
            raise HTTPException(status_code=404, detail="category_not_found")
        return CategoryResponse.model_validate(category, from_attributes=True)

    @router.post("/circuit/reset", response_model=RadarRunResponse)
    def reset_circuit() -> RadarRunResponse:
        RuntimeStateService(session_factory).reset_circuit()
        return RadarRunResponse(status="idle", message="Güvenlik devresi sıfırlandı.")

    return router
