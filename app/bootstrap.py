from app.config import Settings
from app.db.session import SessionFactory
from app.scheduler import ScheduledPipeline
from app.services.analysis import AnalysisService
from app.services.backup import DatabaseBackupService
from app.services.catalog import (
    AKAKCE_CATEGORIES,
    AKAKCE_CATEGORY_PRIORITIES,
    MAIN_CATEGORIES,
    POPULAR_CATEGORY_PRIORITIES,
    VATAN_CATEGORIES,
    VATAN_CATEGORY_PRIORITIES,
    CatalogMonitor,
    CategorySeed,
)
from app.services.collection import MultiSourceCollector, SourceCollection
from app.services.crawl import CrawlService
from app.services.raw_store import RawStore
from app.services.runtime_state import RuntimeStateService
from app.services.source_state import SourceStateService
from app.services.watchlist import WatchlistMonitor
from app.sources.akakce.http import AkakceHttpAdapter
from app.sources.akakce.parser import BASE_URL as AKAKCE_BASE_URL
from app.sources.akakce.parser import extract_external_id as extract_akakce_id
from app.sources.hepsiburada.browser import HepsiburadaBrowserAdapter
from app.sources.vatan.http import VatanHttpAdapter
from app.sources.vatan.parser import BASE_URL as VATAN_BASE_URL
from app.sources.vatan.parser import extract_external_id as extract_vatan_id

CATALOG_PROFILES: dict[str, tuple[tuple[CategorySeed, ...], dict[str, int], bool]] = {
    "akakce": (AKAKCE_CATEGORIES, AKAKCE_CATEGORY_PRIORITIES, False),
    "vatan": (VATAN_CATEGORIES, VATAN_CATEGORY_PRIORITIES, False),
    "hepsiburada": (MAIN_CATEGORIES, POPULAR_CATEGORY_PRIORITIES, True),
}


def build_hepsiburada_crawler(settings: Settings, session_factory: SessionFactory) -> CrawlService:
    return CrawlService(
        settings,
        session_factory,
        lambda: HepsiburadaBrowserAdapter(settings),
    )


def build_akakce_crawler(settings: Settings, session_factory: SessionFactory) -> CrawlService:
    return CrawlService(
        settings,
        session_factory,
        lambda: AkakceHttpAdapter(settings),
        source_name="akakce",
        source_base_url=AKAKCE_BASE_URL,
        robots_url=f"{AKAKCE_BASE_URL}/robots.txt",
        start_url=settings.akakce_start_url,
        start_category="Cep Telefonu",
        external_id_extractor=extract_akakce_id,
    )


def build_vatan_crawler(settings: Settings, session_factory: SessionFactory) -> CrawlService:
    return CrawlService(
        settings,
        session_factory,
        lambda: VatanHttpAdapter(settings),
        source_name="vatan",
        source_base_url=VATAN_BASE_URL,
        robots_url=f"{VATAN_BASE_URL}/robots.txt",
        start_url=settings.vatan_start_url,
        start_category="Notebook",
        external_id_extractor=extract_vatan_id,
    )


def build_pipeline(settings: Settings, session_factory: SessionFactory) -> ScheduledPipeline:
    crawlers: dict[str, CrawlService] = {}
    collections: list[SourceCollection] = []
    if settings.vatan_enabled:
        crawlers["vatan"] = build_vatan_crawler(settings, session_factory)
    if settings.akakce_enabled:
        crawlers["akakce"] = build_akakce_crawler(settings, session_factory)
    if settings.hepsiburada_enabled:
        crawlers["hepsiburada"] = build_hepsiburada_crawler(settings, session_factory)
    primary = next(iter(crawlers.values()), None)
    if primary is None:
        primary = build_vatan_crawler(settings, session_factory)
    for source_name, crawler in crawlers.items():
        seeds, priorities, paginated = CATALOG_PROFILES[source_name]
        catalog = CatalogMonitor(
            session_factory,
            crawler,
            settings.catalog_products_per_page,
            settings.catalog_details_per_page,
            source_name=source_name,
            source_base_url=crawler.source_base_url,
            seeds=seeds,
            priorities=priorities,
            paginated=paginated,
        )
        collections.append(
            SourceCollection(
                source_name=source_name,
                watchlist=WatchlistMonitor(
                    session_factory,
                    crawler,
                    crawlers,
                    source_names=frozenset({source_name}),
                ),
                catalog=catalog,
            )
        )
    source_state = SourceStateService(session_factory)
    collector = MultiSourceCollector(settings, source_state, tuple(collections))
    return ScheduledPipeline(
        settings=settings,
        crawler=primary,
        analyzer=AnalysisService(session_factory),
        backup=DatabaseBackupService(settings),
        retention=RawStore(settings.data_dir / "raw"),
        runtime_state=RuntimeStateService(session_factory),
        catalog=collector,
        watchlist=None,
    )
