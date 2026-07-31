from dataclasses import dataclass

from sqlalchemy import func, select

from app.db.models import Product, Source, WatchTarget
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


MARKETPLACES = (
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
        access_mode="Amazon Creators API",
        access_state="credentials_required",
        state_label="Kimlik bilgisi gerekli",
        description="Resmî erişim yolu belirlendi; bağlayıcı ve hesap anahtarı bekleniyor.",
        requirement="Amazon Associates uygunluğu ve Creators API kimlik bilgileri gerekir.",
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
        product_counts: dict[str, int] = {row[0]: row[1] for row in product_rows}
        watch_counts: dict[str, int] = {row[0]: row[1] for row in watch_rows}
    return [
        MarketplaceView(
            definition=item,
            product_count=int(product_counts.get(item.key, 0)),
            watch_count=int(watch_counts.get(item.key, 0)),
        )
        for item in MARKETPLACES
    ]
