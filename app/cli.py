import asyncio
import json
import threading
import webbrowser
from dataclasses import asdict
from datetime import UTC, datetime

import typer
import uvicorn
from sqlalchemy import Engine, inspect, text

from app.config import Settings
from app.db.migrations import upgrade_database
from app.db.session import build_engine, build_session_factory
from app.domain.crawl import CrawlLimits
from app.scheduler import ScheduledPipeline, serve_scheduler
from app.services.analysis import AnalysisService
from app.services.backup import DatabaseBackupService
from app.services.catalog import CatalogMonitor
from app.services.crawl import CrawlService
from app.services.raw_store import RawStore
from app.services.runtime_state import RuntimeStateService
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


def build_scheduled_pipeline(settings: Settings) -> tuple[ScheduledPipeline, Engine]:
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    crawler = CrawlService(
        settings,
        session_factory,
        lambda: HepsiburadaBrowserAdapter(settings),
    )
    catalog = CatalogMonitor(
        session_factory,
        crawler,
        settings.catalog_products_per_page,
    )
    pipeline = ScheduledPipeline(
        settings=settings,
        crawler=crawler,
        analyzer=AnalysisService(session_factory),
        backup=DatabaseBackupService(settings),
        retention=RawStore(settings.data_dir / "raw"),
        runtime_state=RuntimeStateService(session_factory),
        catalog=catalog,
    )
    return pipeline, engine


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


@app.command("catalog-seed")
def catalog_seed() -> None:
    settings = Settings()
    upgrade_database(settings)
    service, engine = build_crawl_service(settings)
    monitor = CatalogMonitor(
        service.session_factory,
        service,
        settings.catalog_products_per_page,
    )
    try:
        created = monitor.seed()
        typer.echo(json.dumps({"created": created, **asdict(monitor.status())}, default=str))
    finally:
        engine.dispose()


@app.command("catalog-status")
def catalog_status() -> None:
    settings = Settings()
    upgrade_database(settings)
    service, engine = build_crawl_service(settings)
    monitor = CatalogMonitor(
        service.session_factory,
        service,
        settings.catalog_products_per_page,
    )
    try:
        typer.echo(json.dumps(asdict(monitor.status()), ensure_ascii=False, default=str))
    finally:
        engine.dispose()


@app.command("catalog-run")
def catalog_run(
    pages: int = typer.Option(1, min=1, max=10),
) -> None:
    settings = Settings()
    upgrade_database(settings)
    service, engine = build_crawl_service(settings)
    monitor = CatalogMonitor(
        service.session_factory,
        service,
        settings.catalog_products_per_page,
    )
    try:
        summary = asyncio.run(monitor.run_batch(pages))
        output = asdict(summary)
        output["status"] = summary.status.value
        typer.echo(json.dumps(output, ensure_ascii=False))
    finally:
        engine.dispose()


@app.command("catalog-reset")
def catalog_reset(
    confirm: bool = typer.Option(False, "--confirm"),
) -> None:
    if not confirm:
        raise typer.BadParameter("Use --confirm to reset catalog cursors")
    settings = Settings()
    upgrade_database(settings)
    service, engine = build_crawl_service(settings)
    monitor = CatalogMonitor(
        service.session_factory,
        service,
        settings.catalog_products_per_page,
    )
    try:
        typer.echo(json.dumps({"reset": monitor.reset_progress()}))
    finally:
        engine.dispose()


@app.command()
def backup() -> None:
    settings = Settings()
    upgrade_database(settings)
    engine = build_engine(settings)
    try:
        completed_at = datetime.now(UTC)
        result = DatabaseBackupService(settings).create(completed_at)
        RuntimeStateService(build_session_factory(engine)).mark_backup(completed_at)
        typer.echo(
            json.dumps(
                {
                    "path": str(result.path),
                    "size_bytes": result.size_bytes,
                    "integrity": result.integrity,
                    "backups_removed": result.backups_removed,
                },
                ensure_ascii=False,
            )
        )
    finally:
        engine.dispose()


@app.command("prune-raw")
def prune_raw(
    dry_run: bool = typer.Option(True, "--dry-run/--apply"),
) -> None:
    settings = Settings()
    settings.ensure_data_directories()
    result = RawStore(settings.data_dir / "raw").prune(
        settings.raw_retention_days,
        dry_run=dry_run,
    )
    if not dry_run:
        upgrade_database(settings)
        engine = build_engine(settings)
        try:
            RuntimeStateService(build_session_factory(engine)).mark_retention(datetime.now(UTC))
        finally:
            engine.dispose()
    typer.echo(json.dumps(asdict(result), ensure_ascii=False))


@app.command()
def schedule() -> None:
    settings = Settings()
    upgrade_database(settings)
    pipeline, engine = build_scheduled_pipeline(settings)
    try:
        asyncio.run(serve_scheduler(settings, pipeline))
    except KeyboardInterrupt:
        typer.echo("Scheduler stopped")
    finally:
        engine.dispose()


@app.command("scheduled-run")
def scheduled_run() -> None:
    settings = Settings()
    upgrade_database(settings)
    pipeline, engine = build_scheduled_pipeline(settings)
    try:
        result = asyncio.run(pipeline.run())
        typer.echo(json.dumps(asdict(result), ensure_ascii=False))
    finally:
        engine.dispose()


@app.command("runtime-status")
def runtime_status() -> None:
    settings = Settings()
    upgrade_database(settings)
    engine = build_engine(settings)
    try:
        state = RuntimeStateService(build_session_factory(engine)).get()
        typer.echo(json.dumps(asdict(state), ensure_ascii=False, default=str))
    finally:
        engine.dispose()


@app.command("circuit-reset")
def circuit_reset() -> None:
    settings = Settings()
    upgrade_database(settings)
    engine = build_engine(settings)
    try:
        state = RuntimeStateService(build_session_factory(engine)).reset_circuit()
        typer.echo(json.dumps(asdict(state), ensure_ascii=False, default=str))
    finally:
        engine.dispose()


@app.command()
def serve(
    host: str | None = typer.Option(None),
    port: int | None = typer.Option(None),
) -> None:
    settings = Settings()
    upgrade_database(settings)
    uvicorn.run(
        "app.main:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=settings.environment == "development",
    )


@app.command("open-panel")
def open_panel() -> None:
    settings = Settings()
    upgrade_database(settings)
    browser_host = "127.0.0.1" if settings.host in {"0.0.0.0", "::"} else settings.host
    panel_url = f"http://{browser_host}:{settings.port}"
    opener = threading.Timer(1.0, webbrowser.open, args=(panel_url,))
    opener.daemon = True
    opener.start()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    app()
