from pathlib import Path

from sqlalchemy import inspect

from app.config import Settings
from app.db.migrations import upgrade_database
from app.db.session import build_engine

EXPECTED_TABLES = {
    "alembic_version",
    "analyses",
    "crawl_runs",
    "fetches",
    "offers",
    "opportunities",
    "product_snapshots",
    "products",
    "review_labels",
    "reviews",
    "settings",
    "sources",
}


def test_initial_migration_creates_expected_tables(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)

    upgrade_database(settings)
    engine = build_engine(settings)
    try:
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    finally:
        engine.dispose()
