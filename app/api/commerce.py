from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.session import SessionFactory
from app.services.commerce import (
    BusinessCaseInput,
    BusinessCaseView,
    WatchTargetInput,
    WatchTargetView,
    add_watch_target,
    list_business_cases,
    list_watch_targets,
    remove_watch_target,
    save_business_case,
)


class WatchTargetRequest(BaseModel):
    target_type: str
    label: str = Field(min_length=1, max_length=500)
    source_url: str | None = Field(default=None, max_length=2048)
    category: str | None = Field(default=None, max_length=500)
    priority: int = Field(default=3, ge=1, le=5)
    refresh_interval_hours: int = Field(default=24, ge=1, le=168)


class WatchTargetResponse(BaseModel):
    id: int
    product_id: int | None
    target_type: str
    label: str
    source_url: str | None
    category: str | None
    priority: int
    refresh_interval_hours: int
    enabled: bool
    last_checked_at: datetime | None
    last_status: str
    freshness_hours: float | None
    refresh_due: bool
    queue_score: float


class WatchlistResponse(BaseModel):
    items: list[WatchTargetResponse]
    count: int


class BusinessCaseRequest(BaseModel):
    purchase_cost: Decimal | None = Field(default=None, ge=0)
    commission_rate: float = Field(default=0.2, ge=0, lt=1)
    shipping_cost: Decimal = Field(default=Decimal(0), ge=0)
    packaging_cost: Decimal = Field(default=Decimal(0), ge=0)
    advertising_rate: float = Field(default=0.03, ge=0, lt=1)
    return_rate: float = Field(default=0.05, ge=0, lt=1)
    tax_rate: float = Field(default=0, ge=0, lt=1)
    other_cost: Decimal = Field(default=Decimal(0), ge=0)
    target_margin_rate: float = Field(default=0.2, ge=0, lt=1)
    monthly_units: int = Field(default=10, ge=0, le=1000000)
    notes: str | None = Field(default=None, max_length=2000)


class UnitEconomicsResponse(BaseModel):
    sale_price: Decimal | None
    variable_cost: Decimal | None
    contribution: Decimal | None
    margin_rate: float | None
    return_on_cost: float | None
    break_even_price: Decimal | None
    target_sale_price: Decimal | None
    monthly_contribution: Decimal | None
    decision: str


class BusinessCaseResponse(BaseModel):
    product_id: int
    title: str
    source_url: str
    case: BusinessCaseRequest
    economics: UnitEconomicsResponse
    updated_at: datetime


def create_commerce_router(session_factory: SessionFactory) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/watchlist", response_model=WatchlistResponse)
    def watchlist() -> WatchlistResponse:
        items = [watch_target_response(item) for item in list_watch_targets(session_factory)]
        return WatchlistResponse(items=items, count=len(items))

    @router.post("/watchlist", response_model=WatchTargetResponse, status_code=201)
    def create_watch_target(payload: WatchTargetRequest) -> WatchTargetResponse:
        try:
            target = add_watch_target(
                session_factory,
                WatchTargetInput(**payload.model_dump()),
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return watch_target_response(target)

    @router.delete("/watchlist/{target_id}", status_code=204)
    def delete_watch_target(target_id: int) -> None:
        if not remove_watch_target(session_factory, target_id):
            raise HTTPException(status_code=404, detail="watch_target_not_found")

    @router.get("/business-cases", response_model=list[BusinessCaseResponse])
    def business_cases() -> list[BusinessCaseResponse]:
        return [business_case_response(item) for item in list_business_cases(session_factory)]

    @router.put("/business-cases/{product_id}", response_model=BusinessCaseResponse)
    def update_business_case(
        product_id: int,
        payload: BusinessCaseRequest,
    ) -> BusinessCaseResponse:
        try:
            result = save_business_case(
                session_factory,
                product_id,
                BusinessCaseInput(**payload.model_dump()),
            )
        except ValueError as error:
            status_code = 404 if str(error) == "product_not_found" else 422
            raise HTTPException(status_code=status_code, detail=str(error)) from error
        return business_case_response(result)

    return router


def watch_target_response(value: WatchTargetView) -> WatchTargetResponse:
    return WatchTargetResponse.model_validate(value, from_attributes=True)


def business_case_response(value: BusinessCaseView) -> BusinessCaseResponse:
    return BusinessCaseResponse.model_validate(value, from_attributes=True)
