from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db.session import SessionFactory
from app.services.opportunities import list_latest_opportunities


class OpportunityResponse(BaseModel):
    product_id: int
    title: str
    source_url: str
    as_of: datetime
    score: float
    pattern: str | None
    demand: float | None
    satisfaction: float | None
    pain: float | None
    momentum: float | None
    price_position: float | None
    coverage: float
    confidence: float
    reasons: list[dict[str, object]]
    risks: list[str]
    hypothesis: dict[str, object]
    model_version: str


class OpportunityListResponse(BaseModel):
    items: list[OpportunityResponse]
    count: int


def create_opportunities_router(session_factory: SessionFactory) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/opportunities", response_model=OpportunityListResponse)
    def opportunities(limit: int = Query(default=60, ge=1, le=60)) -> OpportunityListResponse:
        items = [
            OpportunityResponse.model_validate(item, from_attributes=True)
            for item in list_latest_opportunities(session_factory, limit)
        ]
        return OpportunityListResponse(items=items, count=len(items))

    return router
