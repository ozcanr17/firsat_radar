from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Fırsat Radar"
    environment: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    admin_username: str = "admin"
    admin_password: SecretStr | None = None
    data_dir: Path = Path("data")
    database_url: str | None = None
    timezone: str = "Europe/Istanbul"
    hepsiburada_start_url: str = "https://www.hepsiburada.com/anne-bebek-oyuncak-c-2147483639"
    hepsiburada_enabled: bool = False
    akakce_enabled: bool = True
    akakce_start_url: str = "https://www.akakce.com/cep-telefonu.html"
    akakce_min_request_seconds: float = Field(default=25.0, ge=10.0, le=120.0)
    akakce_max_request_seconds: float = Field(default=45.0, ge=10.0, le=180.0)
    akakce_rate_limit_cooldown_minutes: int = Field(default=30, ge=5, le=360)
    akakce_daily_request_limit: int = Field(default=400, ge=10, le=2000)
    vatan_enabled: bool = True
    vatan_start_url: str = "https://www.vatanbilgisayar.com/notebook/"
    vatan_min_request_seconds: float = Field(default=15.0, ge=5.0, le=120.0)
    vatan_max_request_seconds: float = Field(default=25.0, ge=5.0, le=180.0)
    vatan_rate_limit_cooldown_minutes: int = Field(default=20, ge=5, le=360)
    vatan_daily_request_limit: int = Field(default=500, ge=10, le=2000)
    browser_channel: str | None = "chrome"
    browser_headless: bool = False
    browser_navigation_timeout_seconds: int = Field(default=20, ge=5, le=60)
    crawl_jitter_min_seconds: float = Field(default=6.0, ge=6.0, le=12.0)
    crawl_jitter_max_seconds: float = Field(default=12.0, ge=6.0, le=12.0)
    crawl_max_pages: int = Field(default=40, ge=1, le=40)
    crawl_max_products: int = Field(default=60, ge=1, le=60)
    crawl_max_details: int = Field(default=20, ge=0, le=20)
    robots_cache_hours: int = Field(default=24, ge=1, le=24)
    scheduler_interval_hours: int = Field(default=1, ge=1, le=168)
    scheduler_products: int = Field(default=200, ge=1, le=500)
    scheduler_details: int = Field(default=5, ge=0, le=20)
    watchlist_enabled: bool = True
    watchlist_targets_per_run: int = Field(default=3, ge=1, le=10)
    embedded_scheduler_enabled: bool = False
    catalog_enabled: bool = True
    catalog_pages_per_run: int = Field(default=3, ge=1, le=10)
    catalog_products_per_page: int = Field(default=60, ge=1, le=60)
    catalog_details_per_page: int = Field(default=2, ge=0, le=5)
    category_discovery_links_per_page: int = Field(default=40, ge=1, le=100)
    category_discovery_max_depth: int = Field(default=6, ge=1, le=10)
    retry_attempts: int = Field(default=2, ge=1, le=3)
    retry_delay_seconds: float = Field(default=30.0, ge=5.0, le=300.0)
    circuit_failure_threshold: int = Field(default=3, ge=1, le=5)
    circuit_cooldown_hours: int = Field(default=24, ge=1, le=72)
    raw_retention_days: int = Field(default=7, ge=1, le=30)
    backup_retention_count: int = Field(default=7, ge=1, le=30)

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
        (self.data_dir / "policy").mkdir(exist_ok=True)
        (self.data_dir / "browser").mkdir(exist_ok=True)
        (self.data_dir / "runtime").mkdir(exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
