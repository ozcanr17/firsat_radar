import csv
import io
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app.config import Settings
from app.db.session import SessionFactory
from app.services.catalog import CatalogMonitor
from app.services.dashboard import get_dashboard_stats
from app.services.opportunities import OpportunityView, list_latest_opportunities
from app.services.product_detail import get_product_page
from app.services.products import ProductView, list_latest_products, search_products
from app.services.recommendations import ROUTE_LABELS, build_recommendations
from app.services.runs import list_runs
from app.services.runtime_state import RuntimeStateService

TEMPLATES_PATH = Path(__file__).with_name("templates")
PATTERN_LABELS = {
    "validated_pain": "Doğrulanmış sorun",
    "validated_demand": "Doğrulanmış talep",
    "price_advantage": "Fiyat avantajı",
    "early_momentum": "Erken ivme",
    "watch": "İzle",
}
TOPIC_LABELS = {
    "delivery": "Teslimat",
    "quality": "Kalite",
    "price": "Fiyat",
    "usability": "Kullanılabilirlik",
    "safety": "Güvenlik",
    "general": "Genel",
}
STATUS_LABELS = {
    "completed": "Tamamlandı",
    "unchanged": "Değişiklik yok",
    "running": "Çalışıyor",
    "blocked": "Engellendi",
    "policy_denied": "Politika reddi",
    "policy_unavailable": "Politika erişilemedi",
    "parser_drift": "Parser sapması",
    "failed": "Başarısız",
    "idle": "Bekliyor",
    "circuit_open": "Devre açık",
    "skipped_overlap": "Çakışma önlendi",
}
METRIC_LABELS = {
    "demand": "Talep",
    "satisfaction": "Memnuniyet",
    "pain": "Sorun yoğunluğu",
    "momentum": "İvme",
    "price_position": "Fiyat konumu",
}
RISK_LABELS = {
    "low_confidence": "Düşük güven",
    "sparse_review_sample": "Sınırlı yorum örneği",
    "momentum_unavailable": "İvme verisi yok",
    "small_market_sample": "Küçük pazar örneği",
}


def create_web_router(settings: Settings, session_factory: SessionFactory) -> APIRouter:
    router = APIRouter()
    templates = Jinja2Templates(directory=TEMPLATES_PATH)

    def local_datetime(value: datetime) -> str:
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
        return aware.astimezone(ZoneInfo(settings.timezone)).strftime("%d.%m.%Y %H:%M")

    templates.env.filters["local_datetime"] = local_datetime

    def shared_context(request: Request, active_page: str) -> dict[str, object]:
        return {
            "request": request,
            "app_name": settings.app_name,
            "environment": settings.environment,
            "active_page": active_page,
            "generated_at": datetime.now(ZoneInfo(settings.timezone)),
            "pattern_labels": PATTERN_LABELS,
            "topic_labels": TOPIC_LABELS,
            "status_labels": STATUS_LABELS,
            "metric_labels": METRIC_LABELS,
            "risk_labels": RISK_LABELS,
        }

    @router.get("/", response_class=HTMLResponse, name="dashboard")
    def dashboard(request: Request) -> HTMLResponse:
        products = list_latest_products(session_factory, 6)
        opportunities = list_latest_opportunities(session_factory, 5)
        context = shared_context(request, "dashboard")
        context.update(
            {
                "stats": get_dashboard_stats(session_factory),
                "data_state": "LIVE_DATA" if products else "NO_DATA",
                "products": products,
                "opportunities": opportunities,
            }
        )
        return templates.TemplateResponse(request=request, name="dashboard.html", context=context)

    @router.get("/products", response_class=HTMLResponse, name="products_page")
    def products_page(
        request: Request,
        q: str = Query(default="", max_length=120),
        category: str = Query(default="", max_length=255),
        sort: str = Query(default="rank", max_length=30),
    ) -> HTMLResponse:
        result = search_products(session_factory, q, category, sort)
        context = shared_context(request, "products")
        context.update(
            {
                "products": result.items,
                "product_total": result.total,
                "categories": result.categories,
                "search_query": q,
                "selected_category": category,
                "selected_sort": sort,
            }
        )
        return templates.TemplateResponse(request=request, name="products.html", context=context)

    @router.get("/products/{product_id}", response_class=HTMLResponse, name="product_page")
    def product_page(request: Request, product_id: int) -> HTMLResponse:
        page = get_product_page(session_factory, product_id)
        if page is None:
            raise HTTPException(status_code=404, detail="Product not found")
        context = shared_context(request, "products")
        context.update({"page": page})
        return templates.TemplateResponse(
            request=request,
            name="product_detail.html",
            context=context,
        )

    @router.get("/opportunities", response_class=HTMLResponse, name="opportunities_page")
    def opportunities_page(request: Request) -> HTMLResponse:
        opportunities = list_latest_opportunities(session_factory)
        context = shared_context(request, "opportunities")
        context.update({"opportunities": opportunities})
        return templates.TemplateResponse(
            request=request,
            name="opportunities.html",
            context=context,
        )

    @router.get("/recommendations", response_class=HTMLResponse, name="recommendations_page")
    def recommendations_page(
        request: Request,
        route: str = Query(default="", max_length=40),
        category: str = Query(default="", max_length=255),
    ) -> HTMLResponse:
        result = build_recommendations(session_factory, route, category)
        context = shared_context(request, "recommendations")
        context.update(
            {
                "recommendations": result.items,
                "route_counts": result.route_counts,
                "route_labels": ROUTE_LABELS,
                "categories": result.categories,
                "selected_route": route,
                "selected_category": category,
            }
        )
        return templates.TemplateResponse(
            request=request,
            name="recommendations.html",
            context=context,
        )

    @router.get("/runs", response_class=HTMLResponse, name="runs_page")
    def runs_page(request: Request) -> HTMLResponse:
        context = shared_context(request, "runs")
        context.update({"runs": list_runs(session_factory)})
        return templates.TemplateResponse(request=request, name="runs.html", context=context)

    @router.get("/settings", response_class=HTMLResponse, name="settings_page")
    def settings_page(request: Request) -> HTMLResponse:
        catalog = CatalogMonitor(
            session_factory,
            None,
            settings.catalog_products_per_page,
            settings.catalog_details_per_page,
        )
        context = shared_context(request, "settings")
        context.update(
            {
                "settings_rows": (
                    ("Kaynak", "Hepsiburada"),
                    ("Başlangıç adresi", settings.hepsiburada_start_url),
                    ("Tarayıcı", settings.browser_channel or "Playwright Chromium"),
                    (
                        "İstek aralığı",
                        f"{settings.crawl_jitter_min_seconds:.0f}-"
                        f"{settings.crawl_jitter_max_seconds:.0f} saniye",
                    ),
                    ("Maksimum ürün", str(settings.crawl_max_products)),
                    ("Maksimum detay", str(settings.crawl_max_details)),
                    ("Robots önbelleği", f"{settings.robots_cache_hours} saat"),
                    ("Zamanlama aralığı", f"{settings.scheduler_interval_hours} saat"),
                    (
                        "Katalog taraması",
                        f"Çalışma başına {settings.catalog_pages_per_run} sayfa / "
                        f"sayfa başına {settings.catalog_details_per_page} detay",
                    ),
                    (
                        "Zamanlı kapsam",
                        f"{settings.scheduler_products} ürün / {settings.scheduler_details} detay",
                    ),
                    ("Retry", f"En fazla {settings.retry_attempts} deneme"),
                    (
                        "Circuit breaker",
                        f"{settings.circuit_failure_threshold} hata / "
                        f"{settings.circuit_cooldown_hours} saat",
                    ),
                    ("Ham kanıt saklama", f"{settings.raw_retention_days} gün"),
                    ("Yedek saklama", f"Son {settings.backup_retention_count} yedek"),
                    ("Veri dizini", str(settings.data_dir.resolve())),
                ),
                "runtime": RuntimeStateService(session_factory).get(),
                "catalog": catalog.status(),
            }
        )
        return templates.TemplateResponse(request=request, name="settings.html", context=context)

    @router.get("/exports/products.csv", name="products_export")
    def products_export() -> Response:
        products = list_latest_products(session_factory)
        return csv_response("firsat-radar-products.csv", products_csv(products))

    @router.get("/exports/opportunities.csv", name="opportunities_export")
    def opportunities_export() -> Response:
        opportunities = list_latest_opportunities(session_factory)
        return csv_response(
            "firsat-radar-opportunities.csv",
            opportunities_csv(opportunities),
        )

    return router


def products_csv(products: list[ProductView]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        (
            "product_id",
            "title",
            "brand",
            "price_try",
            "rating",
            "public_review_count",
            "stored_review_count",
            "opportunity_score",
            "source_url",
            "observed_at",
        )
    )
    for product in products:
        writer.writerow(
            (
                product.id,
                product.title,
                product.brand or "",
                product.price if product.price is not None else "",
                product.rating if product.rating is not None else "",
                product.review_count if product.review_count is not None else "",
                product.stored_review_count,
                product.opportunity_score if product.opportunity_score is not None else "",
                product.source_url,
                product.observed_at.isoformat(),
            )
        )
    return output.getvalue()


def opportunities_csv(opportunities: list[OpportunityView]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        (
            "product_id",
            "title",
            "score",
            "pattern",
            "demand",
            "satisfaction",
            "pain",
            "momentum",
            "price_position",
            "coverage",
            "confidence",
            "risks",
            "source_url",
            "as_of",
        )
    )
    for opportunity in opportunities:
        writer.writerow(
            (
                opportunity.product_id,
                opportunity.title,
                opportunity.score,
                opportunity.pattern or "",
                opportunity.demand if opportunity.demand is not None else "",
                opportunity.satisfaction if opportunity.satisfaction is not None else "",
                opportunity.pain if opportunity.pain is not None else "",
                opportunity.momentum if opportunity.momentum is not None else "",
                opportunity.price_position if opportunity.price_position is not None else "",
                opportunity.coverage,
                opportunity.confidence,
                "|".join(opportunity.risks),
                opportunity.source_url,
                opportunity.as_of.isoformat(),
            )
        )
    return output.getvalue()


def csv_response(filename: str, content: str) -> Response:
    return Response(
        content="\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
