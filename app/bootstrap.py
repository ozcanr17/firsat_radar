from app.config import Settings
from app.db.session import SessionFactory
from app.scheduler import ScheduledPipeline
from app.services.analysis import AnalysisService
from app.services.backup import DatabaseBackupService
from app.services.catalog import CatalogMonitor
from app.services.crawl import CrawlService
from app.services.raw_store import RawStore
from app.services.runtime_state import RuntimeStateService
from app.services.watchlist import WatchlistMonitor
from app.sources.hepsiburada.browser import HepsiburadaBrowserAdapter


def build_pipeline(settings: Settings, session_factory: SessionFactory) -> ScheduledPipeline:
    crawler = CrawlService(
        settings,
        session_factory,
        lambda: HepsiburadaBrowserAdapter(settings),
    )
    catalog = CatalogMonitor(
        session_factory,
        crawler,
        settings.catalog_products_per_page,
        settings.catalog_details_per_page,
    )
    return ScheduledPipeline(
        settings=settings,
        crawler=crawler,
        analyzer=AnalysisService(session_factory),
        backup=DatabaseBackupService(settings),
        retention=RawStore(settings.data_dir / "raw"),
        runtime_state=RuntimeStateService(session_factory),
        catalog=catalog,
        watchlist=WatchlistMonitor(session_factory, crawler),
    )
