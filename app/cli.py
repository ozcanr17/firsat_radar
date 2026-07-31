import json

import typer
import uvicorn
from sqlalchemy import inspect, text

from app.config import Settings
from app.db.migrations import upgrade_database
from app.db.session import build_engine

app = typer.Typer(no_args_is_help=True, add_completion=False)


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
