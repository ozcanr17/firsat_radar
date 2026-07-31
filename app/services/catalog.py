from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CategoryCursor, Source
from app.db.session import SessionFactory
from app.domain.crawl import CrawlLimits, CrawlSummary, RunStatus


@dataclass(frozen=True)
class CategorySeed:
    name: str
    url: str


@dataclass(frozen=True)
class CatalogStatus:
    category_count: int
    enabled_count: int
    pages_scanned: int
    sweeps_completed: int
    pending_count: int
    next_category: str | None
    next_page: int | None
    last_crawled_at: datetime | None


@dataclass(frozen=True)
class CategoryView:
    id: int
    name: str
    url: str
    enabled: bool
    priority: int
    next_page: int
    pages_scanned: int
    sweeps_completed: int
    last_status: str
    last_crawled_at: datetime | None


class TargetCrawler(Protocol):
    async def crawl_target(
        self,
        target_url: str,
        category_name: str,
        limits: CrawlLimits,
    ) -> CrawlSummary: ...


MAIN_CATEGORIES = (
    CategorySeed("Bilgisayar, Tablet", "https://www.hepsiburada.com/bilgisayarlar-c-2147483646"),
    CategorySeed("Telefon", "https://www.hepsiburada.com/telefonlar-c-2147483642"),
    CategorySeed("Ev Elektroniği", "https://www.hepsiburada.com/elektrikli-ev-aletleri-c-17071"),
    CategorySeed(
        "Beyaz Eşya, Mutfak",
        "https://www.hepsiburada.com/beyaz-esya-ankastreler-c-235604",
    ),
    CategorySeed("Fotoğraf, Kamera", "https://www.hepsiburada.com/foto-kameralari-c-2147483606"),
    CategorySeed(
        "Spor, Outdoor",
        "https://www.hepsiburada.com/spor-outdoor-urunleri-c-60001546",
    ),
    CategorySeed("Giyim, Ayakkabı", "https://www.hepsiburada.com/giyim-ayakkabi-c-2147483636"),
    CategorySeed(
        "Altın, Takı, Mücevher",
        "https://www.hepsiburada.com/altin-taki-mucevherler-c-2147483617",
    ),
    CategorySeed(
        "Kozmetik, Kişisel Bakım",
        "https://www.hepsiburada.com/kozmetik-kisisel-bakim-urunleri-c-60001547",
    ),
    CategorySeed(
        "Anne, Bebek, Oyuncak",
        "https://www.hepsiburada.com/anne-bebek-oyuncak-c-2147483639",
    ),
    CategorySeed(
        "Kitap, Film, Müzik",
        "https://www.hepsiburada.com/kitaplar-filmler-muzikler-c-60001501",
    ),
    CategorySeed(
        "Hobi, Oyun Konsolları",
        "https://www.hepsiburada.com/hobi-oyun-konsollari-c-60003054",
    ),
    CategorySeed(
        "Yapı Market, Bahçe, Oto",
        "https://www.hepsiburada.com/yapi-market-bahce-oto-c-60002705",
    ),
    CategorySeed("Ev Dekorasyon", "https://www.hepsiburada.com/ev-dekorasyon-c-60002028"),
    CategorySeed("Petshop", "https://www.hepsiburada.com/pet-shop-c-2147483616"),
    CategorySeed("Süpermarket", "https://www.hepsiburada.com/supermarket-c-2147483619"),
    CategorySeed("Akıllı Ev, Yaşam", "https://www.hepsiburada.com/akilli-ev-yasam-c-80079038"),
)

POPULAR_CATEGORY_PRIORITIES = {
    "Bilgisayar, Tablet": 1000,
    "Telefon": 950,
    "Ev Elektroniği": 900,
    "Beyaz Eşya, Mutfak": 850,
    "Anne, Bebek, Oyuncak": 800,
    "Kozmetik, Kişisel Bakım": 750,
    "Süpermarket": 700,
    "Spor, Outdoor": 650,
}


class CatalogMonitor:
    def __init__(
        self,
        session_factory: SessionFactory,
        crawler: TargetCrawler | None,
        products_per_page: int,
        details_per_page: int = 0,
    ) -> None:
        self.session_factory = session_factory
        self.crawler = crawler
        self.products_per_page = products_per_page
        self.details_per_page = details_per_page

    def seed(self) -> int:
        created = 0
        with self.session_factory.begin() as session:
            source = session.scalar(select(Source).where(Source.name == "hepsiburada"))
            if source is None:
                source = Source(
                    name="hepsiburada",
                    base_url="https://www.hepsiburada.com",
                    enabled=True,
                    policy_state="unknown",
                )
                session.add(source)
                session.flush()
            for seed in MAIN_CATEGORIES:
                priority = POPULAR_CATEGORY_PRIORITIES.get(seed.name, 500)
                existing = session.scalar(
                    select(CategoryCursor).where(
                        CategoryCursor.source_id == source.id,
                        CategoryCursor.url == seed.url,
                    )
                )
                if existing is not None:
                    existing.name = seed.name
                    existing.priority = priority
                    continue
                session.add(
                    CategoryCursor(
                        source_id=source.id,
                        name=seed.name,
                        url=seed.url,
                        enabled=True,
                        priority=priority,
                        next_page=1,
                        pages_scanned=0,
                        sweeps_completed=0,
                        last_status="pending",
                    )
                )
                created += 1
        return created

    def categories(self) -> list[CategoryView]:
        self.seed()
        with self.session_factory() as session:
            rows = session.scalars(
                select(CategoryCursor).order_by(
                    CategoryCursor.priority.desc(),
                    CategoryCursor.name,
                )
            ).all()
        return [
            CategoryView(
                id=row.id,
                name=row.name,
                url=row.url,
                enabled=row.enabled,
                priority=row.priority,
                next_page=row.next_page,
                pages_scanned=row.pages_scanned,
                sweeps_completed=row.sweeps_completed,
                last_status=row.last_status,
                last_crawled_at=row.last_crawled_at,
            )
            for row in rows
        ]

    def set_enabled(self, category_id: int, enabled: bool) -> CategoryView | None:
        self.seed()
        with self.session_factory.begin() as session:
            category = session.get(CategoryCursor, category_id)
            if category is None:
                return None
            category.enabled = enabled
        return next(item for item in self.categories() if item.id == category_id)

    async def run_batch(self, page_count: int) -> CrawlSummary:
        self.seed()
        if self.status().enabled_count == 0:
            return CrawlSummary(
                run_id=0,
                status=RunStatus.UNCHANGED,
                products_seen=0,
                products_created=0,
                products_updated=0,
                snapshots_created=0,
                details_created=0,
                reviews_created=0,
                fetches_created=0,
                error_code=None,
                listing_signature=None,
            )
        summaries: list[CrawlSummary] = []
        for _ in range(page_count):
            summary = await self.run_next()
            summaries.append(summary)
            if summary.status not in {RunStatus.COMPLETED, RunStatus.UNCHANGED}:
                break
        return self._aggregate(summaries)

    async def run_next(self) -> CrawlSummary:
        category = self._next_category()
        if category is None:
            raise RuntimeError("No enabled catalog category")
        if self.crawler is None:
            raise RuntimeError("Catalog crawler is unavailable")
        page = category.next_page
        target_url = category_page_url(category.url, page)
        summary = await self.crawler.crawl_target(
            target_url,
            category.name,
            CrawlLimits(
                products=self.products_per_page,
                details=self.details_per_page,
            ),
        )
        self._advance(category.id, page, summary)
        return summary

    def status(self) -> CatalogStatus:
        self.seed()
        with self.session_factory() as session:
            category_count = session.scalar(select(func.count()).select_from(CategoryCursor)) or 0
            enabled_count = (
                session.scalar(
                    select(func.count()).select_from(CategoryCursor).where(CategoryCursor.enabled)
                )
                or 0
            )
            pages_scanned = session.scalar(select(func.sum(CategoryCursor.pages_scanned))) or 0
            sweeps_completed = (
                session.scalar(select(func.sum(CategoryCursor.sweeps_completed))) or 0
            )
            pending_count = (
                session.scalar(
                    select(func.count())
                    .select_from(CategoryCursor)
                    .where(CategoryCursor.enabled, CategoryCursor.sweeps_completed == 0)
                )
                or 0
            )
            next_category = self._next_category_in_session(session)
            last_crawled_at = session.scalar(select(func.max(CategoryCursor.last_crawled_at)))
        return CatalogStatus(
            category_count=category_count,
            enabled_count=enabled_count,
            pages_scanned=pages_scanned,
            sweeps_completed=sweeps_completed,
            pending_count=pending_count,
            next_category=next_category.name if next_category else None,
            next_page=next_category.next_page if next_category else None,
            last_crawled_at=last_crawled_at,
        )

    def reset_progress(self) -> int:
        with self.session_factory.begin() as session:
            categories = session.scalars(select(CategoryCursor)).all()
            for category in categories:
                category.next_page = 1
                category.page_size = None
                category.pages_scanned = 0
                category.sweeps_completed = 0
                category.last_signature = None
                category.last_status = "pending"
                category.last_crawled_at = None
                category.last_completed_at = None
            return len(categories)

    def _next_category(self) -> CategoryCursor | None:
        with self.session_factory() as session:
            category = self._next_category_in_session(session)
            if category is None:
                return None
            session.expunge(category)
            return category

    @staticmethod
    def _next_category_in_session(session: Session) -> CategoryCursor | None:
        return session.scalar(
            select(CategoryCursor)
            .where(CategoryCursor.enabled)
            .order_by(
                CategoryCursor.last_crawled_at.is_not(None),
                CategoryCursor.last_crawled_at,
                CategoryCursor.priority.desc(),
                CategoryCursor.id,
            )
            .limit(1)
        )

    def _advance(self, category_id: int, page: int, summary: CrawlSummary) -> None:
        now = datetime.now(UTC)
        with self.session_factory.begin() as session:
            category = session.get_one(CategoryCursor, category_id)
            category.last_status = summary.status.value
            category.last_crawled_at = now
            if summary.status not in {RunStatus.COMPLETED, RunStatus.UNCHANGED}:
                return
            repeated_page = bool(
                page > 1
                and summary.listing_signature
                and summary.listing_signature == category.last_signature
            )
            category.pages_scanned += 1
            if page == 1 and summary.products_seen > 0:
                category.page_size = summary.products_seen
                category.next_page = 2
                category.last_signature = summary.listing_signature
                return
            end_of_category = (
                summary.products_seen == 0
                or repeated_page
                or bool(category.page_size and summary.products_seen < category.page_size)
            )
            if end_of_category:
                category.next_page = 1
                category.sweeps_completed += 1
                category.last_completed_at = now
                category.last_signature = None
                return
            category.next_page = page + 1
            category.last_signature = summary.listing_signature

    @staticmethod
    def _aggregate(summaries: list[CrawlSummary]) -> CrawlSummary:
        if not summaries:
            raise RuntimeError("Catalog batch is empty")
        last = summaries[-1]
        successful = all(
            summary.status in {RunStatus.COMPLETED, RunStatus.UNCHANGED} for summary in summaries
        )
        status = (
            RunStatus.COMPLETED
            if successful and any(summary.status is RunStatus.COMPLETED for summary in summaries)
            else last.status
        )
        return CrawlSummary(
            run_id=last.run_id,
            status=status,
            products_seen=sum(summary.products_seen for summary in summaries),
            products_created=sum(summary.products_created for summary in summaries),
            products_updated=sum(summary.products_updated for summary in summaries),
            snapshots_created=sum(summary.snapshots_created for summary in summaries),
            details_created=sum(summary.details_created for summary in summaries),
            reviews_created=sum(summary.reviews_created for summary in summaries),
            fetches_created=sum(summary.fetches_created for summary in summaries),
            error_code=last.error_code,
            listing_signature=None,
        )


def category_page_url(url: str, page: int) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if page > 1:
        query["sayfa"] = str(page)
    else:
        query.pop("sayfa", None)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
