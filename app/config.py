from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fırsat Radar"
    environment: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = Path("data")
    database_url: str | None = None
    timezone: str = "Europe/Istanbul"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FIRSAT_RADAR_",
        extra="ignore",
    )

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        database_path = (self.data_dir / "firsat_radar.db").resolve()
        return f"sqlite:///{database_path.as_posix()}"

    def ensure_data_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "backups").mkdir(exist_ok=True)
        (self.data_dir / "raw").mkdir(exist_ok=True)
        (self.data_dir / "exports").mkdir(exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
