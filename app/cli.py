import asyncio
import json
from dataclasses import asdict

import typer
import uvicorn
from sqlalchemy import Engine, inspect, text

from app.config import Settings
from app.db.migrations import upgrade_database
from app.db.session import build_engine, build_session_factory
from app.domain.crawl import CrawlLimits
from app.services.analysis import AnalysisService
from app.services.crawl import CrawlService
from app.sources.hepsiburada.browser import HepsiburadaBrowserAdapter

app = typer.Typer(no_args_is_help=True, add_completion=False)


def build_crawl_service(settings: Settings) -> tuple[CrawlService, Engine]:
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    service = CrawlService(
        settings,
        session_factory,
        lambda: HepsiburadaBrowserAdapter(settings),
    )
    return service, engine


def validate_source(source: str) -> None:
    if source != "hepsiburada":
        raise typer.BadParameter("Only hepsiburada is available")


@app.command("init-db")
def init_db() -> None:
    settings = Settings()
    upgrade_database(settings)
    typer.echo(f"Database ready: {settings.resolved_database_url}")


@app.command()
def doctor() -> None:
    settings = Settings()
    settings.ensure_data_directories()
    engine = build_engine(settings)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = inspect(connection).get_table_names()
        result = {
            "status": "ok",
            "database": settings.resolved_database_url,
            "migration_ready": "sources" in tables,
            "data_directory": str(settings.data_dir.resolve()),
        }
        typer.echo(json.dumps(result, ensure_ascii=False))
    finally:
        engine.dispose()


@app.command("policy-check")
def policy_check(
    source: str = typer.Option("hepsiburada"),
) -> None:
    validate_source(source)
    settings = Settings()
    upgrade_database(settings)
    service, engine = build_crawl_service(settings)
    try:
        decision = asyncio.run(service.policy_check())
        typer.echo(
            json.dumps(
                {
                    "source": source,
                    "state": decision.state.value,
                    "target_url": decision.url,
                    "checked_at": decision.checked_at.isoformat(),
                    "status_code": decision.status_code,
                    "cached": decision.cached,
                    "reason_code": decision.reason_code,
                },
                ensure_ascii=False,
            )
        )
    finally:
        engine.dispose()


@app.command()
def crawl(
    source: str = typer.Option("hepsiburada"),
    limit_products: int = typer.Option(20, min=1, max=60),
    limit_details: int = typer.Option(0, min=0, max=20),
) -> None:
    validate_source(source)
    settings = Settings()
    upgrade_database(settings)
    service, engine = build_crawl_service(settings)
    try:
        summary = asyncio.run(
            service.crawl(CrawlLimits(products=limit_products, details=limit_details))
        )
        output = asdict(summary)
        output["status"] = summary.status.value
        typer.echo(json.dumps(output, ensure_ascii=False))
    finally:
        engine.dispose()


@app.command()
def analyze(
    limit_products: int = typer.Option(60, min=1, max=60),
) -> None:
    settings = Settings()
    upgrade_database(settings)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    try:
        summary = AnalysisService(session_factory).analyze(limit_products)
        typer.echo(json.dumps(asdict(summary), ensure_ascii=False))
    finally:
        engine.dispose()


@app.command()
def serve(
    host: str | None = typer.Option(None),
    port: int | None = typer.Option(None),
) -> None:
    settings = Settings()
    uvicorn.run(
        "app.main:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=settings.environment == "development",
    )


if __name__ == "__main__":
    app()
