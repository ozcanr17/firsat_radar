from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db.session import SessionFactory
from app.services.products import list_latest_products


class ProductResponse(BaseModel):
    id: int
    title: str
    source_url: str
    image_url: str | None
    observed_at: datetime
    fetch_id: int
    price: Decimal | None
    rating: float | None
    review_count: int | None
    rank: int | None
    coverage: float
    confidence: float


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    count: int


def create_products_router(session_factory: SessionFactory) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/products", response_model=ProductListResponse)
    def products(limit: int = Query(default=60, ge=1, le=60)) -> ProductListResponse:
        items = [
            ProductResponse.model_validate(product, from_attributes=True)
            for product in list_latest_products(session_factory, limit)
        ]
        return ProductListResponse(items=items, count=len(items))

    return router
