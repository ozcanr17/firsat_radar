from dataclasses import dataclass
from decimal import Decimal

from app.db.session import SessionFactory
from app.services.commerce import UnitEconomics, list_business_cases
from app.services.opportunities import OpportunityView, list_latest_opportunities
from app.services.products import ProductView, list_latest_products


@dataclass(frozen=True)
class BusinessRecommendation:
    product_id: int
    title: str
    category: str | None
    source_url: str
    price: Decimal | None
    route: str
    route_label: str
    readiness: float
    confidence: float
    summary: str
    evidence: tuple[str, ...]
    risks: tuple[str, ...]
    validation_steps: tuple[str, ...]
    economics: UnitEconomics | None


@dataclass(frozen=True)
class RecommendationResult:
    items: list[BusinessRecommendation]
    route_counts: dict[str, int]
    categories: list[str]


ROUTE_LABELS = {
    "resale": "Al-sat adayı",
    "local_production": "Yerel üretim adayı",
    "watch": "Yakından izle",
    "avoid": "Şimdilik uzak dur",
    "research": "Önce veri topla",
}
RISK_LABELS = {
    "low_confidence": "Kanıt güveni düşük",
    "sparse_review_sample": "Kayıtlı yorum örneği sınırlı",
    "momentum_unavailable": "Zaman içindeki ivme henüz ölçülemiyor",
    "small_market_sample": "Karşılaştırılan pazar örneği küçük",
}


def build_recommendations(
    session_factory: SessionFactory,
    route: str = "",
    category: str = "",
    limit: int = 100,
) -> RecommendationResult:
    products = {product.id: product for product in list_latest_products(session_factory, 500)}
    economics = {item.product_id: item.economics for item in list_business_cases(session_factory)}
    recommendations = [
        recommend(
            opportunity,
            products[opportunity.product_id],
            economics.get(opportunity.product_id),
        )
        for opportunity in list_latest_opportunities(session_factory, 500)
        if opportunity.product_id in products
    ]
    route_counts = {
        route_name: sum(item.route == route_name for item in recommendations)
        for route_name in ROUTE_LABELS
    }
    categories = sorted({item.category for item in recommendations if item.category})
    if route:
        recommendations = [item for item in recommendations if item.route == route]
    if category:
        recommendations = [item for item in recommendations if item.category == category]
    recommendations.sort(key=lambda item: (route_priority(item.route), -item.readiness, item.title))
    return RecommendationResult(
        items=recommendations[:limit],
        route_counts=route_counts,
        categories=categories,
    )


def recommend(
    opportunity: OpportunityView,
    product: ProductView,
    economics: UnitEconomics | None = None,
) -> BusinessRecommendation:
    route = resolve_route(opportunity, product)
    readiness = round(
        opportunity.score * 0.4
        + opportunity.confidence * 100.0 * 0.4
        + opportunity.coverage * 100.0 * 0.2,
        1,
    )
    return BusinessRecommendation(
        product_id=product.id,
        title=product.title,
        category=product.category,
        source_url=product.source_url,
        price=product.price,
        route=route,
        route_label=ROUTE_LABELS[route],
        readiness=readiness,
        confidence=opportunity.confidence,
        summary=route_summary(route),
        evidence=build_evidence(opportunity, product, economics),
        risks=build_risks(opportunity, product, route, economics),
        validation_steps=validation_steps(route),
        economics=economics,
    )


def resolve_route(opportunity: OpportunityView, product: ProductView) -> str:
    if opportunity.confidence < 0.45 or opportunity.coverage < 0.6:
        return "research"
    if (
        at_least(opportunity.demand, 60)
        and at_least(opportunity.pain, 30)
        and product.stored_review_count >= 10
    ):
        return "local_production"
    if at_least(opportunity.demand, 50) and at_least(opportunity.satisfaction, 80):
        return "resale"
    if below(opportunity.satisfaction, 65) or at_least(opportunity.pain, 60):
        return "avoid"
    if at_least(opportunity.momentum, 50):
        return "watch"
    return "research"


def build_evidence(
    opportunity: OpportunityView,
    product: ProductView,
    economics: UnitEconomics | None = None,
) -> tuple[str, ...]:
    evidence = []
    if product.review_count is not None:
        evidence.append(f"{product.review_count:,} herkese açık değerlendirme")
    if product.rating is not None:
        evidence.append(f"5 üzerinden {product.rating:.1f} puan")
    if opportunity.demand is not None:
        evidence.append(f"Talep skoru {opportunity.demand:.0f}/100")
    if opportunity.pain is not None:
        evidence.append(f"Sorun yoğunluğu {opportunity.pain:.0f}/100")
    if opportunity.momentum is not None:
        evidence.append(f"İvme skoru {opportunity.momentum:.0f}/100")
    if economics and economics.margin_rate is not None:
        evidence.append(f"Hesaplanan net marj %{economics.margin_rate * 100:.1f}")
    return tuple(evidence[:4])


def build_risks(
    opportunity: OpportunityView,
    product: ProductView,
    route: str,
    economics: UnitEconomics | None = None,
) -> tuple[str, ...]:
    risks = [RISK_LABELS.get(risk, risk) for risk in opportunity.risks]
    if route in {"resale", "local_production"} and economics is None:
        risks.append("Komisyon, lojistik, iade ve vergi sonrası marj doğrulanmadı")
    if economics and economics.decision == "no_go":
        risks.append("Girilen maliyetlerle hedef marj karşılanmıyor")
    if route == "local_production":
        risks.append("Üretilebilirlik, mevzuat ve sertifikasyon gereksinimleri doğrulanmadı")
    if product.detail_coverage is None:
        risks.append("Ürün detayı ve nitelikleri henüz toplanmadı")
    return tuple(dict.fromkeys(risks))


def validation_steps(route: str) -> tuple[str, ...]:
    return {
        "resale": (
            "En az üç tedarikçiden teslim edilmiş birim maliyet al",
            "Komisyon, kargo, iade ve vergi sonrası net marjı hesapla",
            "10-20 adetlik küçük stokla dönüşüm ve iade oranını test et",
        ),
        "local_production": (
            "Olumsuz yorumları tekrar eden ihtiyaç başlıklarına ayır",
            "Hedef maliyet ve satış fiyatıyla basit bir prototip çıkar",
            "En az 20 potansiyel kullanıcıyla problem ve ödeme isteğini doğrula",
        ),
        "watch": (
            "İki yeni fiyat ve değerlendirme snapshot'ı bekle",
            "Rakip sayısı ve satıcı yoğunluğundaki değişimi kontrol et",
            "İvme devam ederse küçük pilot ekonomisini hesapla",
        ),
        "avoid": (
            "Sorun sinyalinin geçici olup olmadığını yeni yorumlarla kontrol et",
            "İade, garanti ve mevzuat risklerini ayrı hesapla",
            "Kanıt belirgin biçimde iyileşmeden sermaye bağlama",
        ),
        "research": (
            "Ürün detayını ve ürün sayfasında görünür yorum örneğini topla",
            "En az iki farklı tarihte fiyat ve değerlendirme snapshot'ı oluştur",
            "Tedarik maliyeti ve rakip satıcı sayısını manuel doğrula",
        ),
    }[route]


def route_summary(route: str) -> str:
    return {
        "resale": "Talep ve memnuniyet güçlü; küçük stoklu al-sat testi değerlendirilebilir.",
        "local_production": (
            "Talep ile tekrarlanan sorun birlikte; daha iyi yerel alternatif araştırılabilir."
        ),
        "watch": "Erken hareket sinyali var; sermaye bağlamadan yeni snapshot'ları izle.",
        "avoid": "Mevcut memnuniyet veya sorun sinyali sermaye bağlamak için elverişli değil.",
        "research": "Ticari yön seçmek için detay, yorum veya zaman serisi kanıtı yetersiz.",
    }[route]


def route_priority(route: str) -> int:
    return {
        "local_production": 0,
        "resale": 1,
        "watch": 2,
        "research": 3,
        "avoid": 4,
    }[route]


def at_least(value: float | None, threshold: float) -> bool:
    return value is not None and value >= threshold


def below(value: float | None, threshold: float) -> bool:
    return value is not None and value < threshold
