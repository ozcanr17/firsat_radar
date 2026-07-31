from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.commerce import create_commerce_router
from app.api.health import create_health_router
from app.api.opportunities import create_opportunities_router
from app.api.products import create_products_router
from app.bootstrap import build_pipeline
from app.config import Settings, get_settings
from app.db.migrations import upgrade_database
from app.db.session import build_engine, build_session_factory
from app.scheduler import build_scheduler
from app.web.auth import BasicAuthMiddleware
from app.web.router import create_web_router

STATIC_PATH = Path(__file__).parent / "web" / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    active_settings.ensure_data_directories()
    upgrade_database(active_settings)
    engine = build_engine(active_settings)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        scheduler = None
        if active_settings.embedded_scheduler_enabled:
            scheduler = build_scheduler(
                active_settings,
                build_pipeline(active_settings, session_factory),
            )
            scheduler.start()
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)
            engine.dispose()

    application = FastAPI(title=active_settings.app_name, lifespan=lifespan)
    if active_settings.admin_password is not None:
        application.add_middleware(
            BasicAuthMiddleware,
            username=active_settings.admin_username,
            password=active_settings.admin_password.get_secret_value(),
        )
    application.state.settings = active_settings
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.include_router(create_health_router(session_factory))
    application.include_router(create_commerce_router(session_factory))
    application.include_router(create_products_router(session_factory))
    application.include_router(create_opportunities_router(session_factory))
    application.include_router(create_web_router(active_settings, session_factory))
    application.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")
    return application


app = create_app()
