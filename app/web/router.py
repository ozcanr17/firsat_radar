from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import Settings

TEMPLATES_PATH = Path(__file__).with_name("templates")


def create_web_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_PATH)

    @router.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "app_name": settings.app_name,
                "environment": settings.environment,
                "data_state": "NO_DATA",
            },
        )

    return router
