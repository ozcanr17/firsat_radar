from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import Settings
from app.db.session import SessionFactory
from app.services.products import list_latest_products

TEMPLATES_PATH = Path(__file__).with_name("templates")


def create_web_router(settings: Settings, session_factory: SessionFactory) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_PATH)

    @router.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        products = list_latest_products(session_factory, 20)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "app_name": settings.app_name,
                "environment": settings.environment,
                "data_state": "LIVE_DATA" if products else "NO_DATA",
                "products": products,
            },
        )

    return router
