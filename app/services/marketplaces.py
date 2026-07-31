from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

from app.db.models import Product, Source, SourceRuntimeState, WatchTarget
from app.db.session import SessionFactory


@dataclass(frozen=True)
class MarketplaceDefinition:
    key: str
    label: str
    base_url: str
    access_mode: str
    access_state: str
    state_label: str
    description: str
    requirement: str
    documentation_url: str | None
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class MarketplaceView:
    definition: MarketplaceDefinition
    product_count: int
    watch_count: int
    runtime_status: str = "idle"
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    circuit_open_until: datetime | None = None
    last_error_code: str | None = None

    @property
    def runtime_label(self) -> str:
        return RUNTIME_LABELS.get(self.runtime_status, self.runtime_status)


MARKETPLACES = (
    MarketplaceDefinition(
        key="akakce",
        label="Akakçe",
        base_url="https://www.akakce.com",
        access_mode="robots.txt izinli HTTP + yapısal veri",
        access_state="active",
        state_label="Çalışıyor",
        description=(
            "Kategori sayfalarından ürünleri, ürün sayfalarından ise tüm satıcıların "
            "fiyat, stok ve teslimat kanıtlarını toplar."
        ),
        requirement="robots.txt izin verdiği sürece ek kimlik bilgisi gerekmez.",
        documentation_url="https://www.akakce.com/robots.txt",
        capabilities=(
            "Kategori keşfi",
            "Pazar yerleri arası fiyat karşılaştırma",
            "Satıcı yoğunluğu",
        ),
    ),
    MarketplaceDefinition(
        key="vatan",
        label="Vatan Bilgisayar",
        base_url="https://www.vatanbilgisayar.com",
        access_mode="robots.txt izinli HTTP + yapısal veri",
        access_state="active",
        state_label="Çalışıyor",
        description=(
            "Kategori sayfalarından ürünleri; ürün sayfalarından fiyat, stok, puan, "
            "marka ve üretici kodu (MPN) kanıtlarını toplar."
        ),
        requirement="robots.txt izin verdiği sürece ek kimlik bilgisi gerekmez.",
        documentation_url="https://www.vatanbilgisayar.com/robots.txt",
        capabilities=("Kategori keşfi", "Fiyat geçmişi", "Ürün kimliği (MPN) eşleme"),
    ),
    MarketplaceDefinition(
        key="hepsiburada",
        label="Hepsiburada",
        base_url="https://www.hepsiburada.com",
        access_mode="Görünür tarayıcı + izinli sayfalar",
        access_state="active",
        state_label="Çalışıyor",
        description="Ürün sayfasındaki fiyat, puan, görünür yorum ve kanıtları toplar.",
        requirement="Bilinen ürün hedefleri erişim politikası uygun kaldığı sürece çalışır.",
        documentation_url=None,
        capabilities=("Ürün takibi", "Fiyat geçmişi", "Görünür yorum analizi"),
    ),
    MarketplaceDefinition(
        key="amazon_tr",
        label="Amazon Türkiye",
        base_url="https://www.amazon.com.tr",
        access_mode="Resmî API veya yazılı izin",
        access_state="credentials_required",
        state_label="Yetkili erişim gerekli",
        description=(
            "Kategori hedefi ve düğüm kimliği kaydedilir; izinsiz sayfa robotu çalıştırılmaz."
        ),
        requirement="Creators API kimlik bilgisi veya Amazon'dan yazılı otomasyon izni gerekir.",
        documentation_url="https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction",
        capabilities=("Ürün arama", "Ürün detayları", "Kategori düğümleri"),
    ),
    MarketplaceDefinition(
        key="trendyol",
        label="Trendyol",
        base_url="https://www.trendyol.com",
        access_mode="Onaylı veri akışı veya iş ortaklığı",
        access_state="agreement_required",
        state_label="Erişim anlaşması gerekli",
        description="Mağaza yönetim API'si tüm pazar araştırması için açık katalog sağlamıyor.",
        requirement="Onaylı katalog/affiliate veri akışı veya yazılı izin gerekir.",
        documentation_url="https://developers.trendyol.com/docs/getting-started",
        capabilities=("Hedef kaydı", "Onaylı feed alımı", "Mağaza verisi eşleme"),
    ),
    MarketplaceDefinition(
        key="mediamarkt_tr",
        label="MediaMarkt Türkiye",
        base_url="https://www.mediamarkt.com.tr",
        access_mode="Affiliate veya katalog veri akışı",
        access_state="agreement_required",
        state_label="Erişim anlaşması gerekli",
        description="Kamuya açık pazar kataloğu API'si yerine izinli veri akışı bekleniyor.",
        requirement="MediaMarkt veya affiliate ağı üzerinden katalog erişimi gerekir.",
        documentation_url=None,
        capabilities=("Hedef kaydı", "Feed alımı", "Fiyat karşılaştırma"),
    ),
)
MARKETPLACE_BY_KEY = {item.key: item for item in MARKETPLACES}

RUNTIME_LABELS = {
    "idle": "Henüz çalışmadı",
    "running": "Çalışıyor",
    "completed": "Son tarama başarılı",
    "failed": "Son tarama başarısız",
    "throttled": "Hız sınırı nedeniyle bekliyor",
    "circuit_open": "Devre kesici açık",
}


def list_marketplaces(session_factory: SessionFactory) -> list[MarketplaceView]:
    with session_factory() as session:
        product_rows = session.execute(
            select(Source.name, func.count(Product.id))
            .outerjoin(Product, Product.source_id == Source.id)
            .group_by(Source.name)
        ).all()
        watch_rows = session.execute(
            select(WatchTarget.source_name, func.count(WatchTarget.id)).group_by(
                WatchTarget.source_name
            )
        ).all()
        runtime_rows = session.scalars(select(SourceRuntimeState)).all()
        product_counts: dict[str, int] = {row[0]: row[1] for row in product_rows}
        watch_counts: dict[str, int] = {row[0]: row[1] for row in watch_rows}
        runtime_by_source = {row.source_name: row for row in runtime_rows}
        return [
            MarketplaceView(
                definition=item,
                product_count=int(product_counts.get(item.key, 0)),
                watch_count=int(watch_counts.get(item.key, 0)),
                runtime_status=(
                    runtime_by_source[item.key].status if item.key in runtime_by_source else "idle"
                ),
                last_run_at=(
                    runtime_by_source[item.key].last_run_at
                    if item.key in runtime_by_source
                    else None
                ),
                last_success_at=(
                    runtime_by_source[item.key].last_success_at
                    if item.key in runtime_by_source
                    else None
                ),
                circuit_open_until=(
                    runtime_by_source[item.key].circuit_open_until
                    if item.key in runtime_by_source
                    else None
                ),
                last_error_code=(
                    runtime_by_source[item.key].last_error_code
                    if item.key in runtime_by_source
                    else None
                ),
            )
            for item in MARKETPLACES
        ]
