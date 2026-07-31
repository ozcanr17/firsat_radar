from pathlib import Path

from app.config import Settings


def test_database_url_uses_configured_data_directory(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)

    assert settings.resolved_database_url == f"sqlite:///{tmp_path / 'firsat_radar.db'}"


def test_data_directories_are_created(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)

    settings.ensure_data_directories()

    assert (tmp_path / "backups").is_dir()
    assert (tmp_path / "raw").is_dir()
    assert (tmp_path / "exports").is_dir()
    assert (tmp_path / "runtime").is_dir()
