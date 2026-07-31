from pathlib import Path

from alembic.config import Config

from alembic import command
from app.config import Settings


def upgrade_database(settings: Settings) -> None:
    settings.ensure_data_directories()
    project_root = Path(__file__).resolve().parents[2]
    config = Config(project_root / "alembic.ini")
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.resolved_database_url.replace("%", "%%"))
    command.upgrade(config, "head")
