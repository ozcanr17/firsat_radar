from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings
from app.db.session import build_engine, build_session_factory
from app.services.products import list_latest_products
from app.services.recommendations import ROUTE_LABELS, build_recommendations


@dataclass(frozen=True)
class StaticExportResult:
    output_path: Path
    products: int
    recommendations: int


def export_static_site(settings: Settings, output_directory: Path) -> StaticExportResult:
    engine = build_engine(settings)
    try:
        session_factory = build_session_factory(engine)
        products = [
            product
            for product in list_latest_products(session_factory, 500)
            if product.category and "anne" in product.category.casefold()
        ]
        recommendation_result = build_recommendations(session_factory, limit=100)
        product_ids = {product.id for product in products}
        recommendations = [
            item for item in recommendation_result.items if item.product_id in product_ids
        ]
    finally:
        engine.dispose()
    templates_path = Path(__file__).parents[1] / "web" / "templates"
    environment = Environment(
        loader=FileSystemLoader(templates_path),
        autoescape=select_autoescape(("html",)),
    )
    template = environment.get_template("static_site.html")
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / "index.html"
    output_path.write_text(
        template.render(
            generated_at=datetime.now(ZoneInfo(settings.timezone)),
            products=products,
            recommendations=recommendations,
            route_counts={
                route: sum(item.route == route for item in recommendations)
                for route in ROUTE_LABELS
            },
            route_labels=ROUTE_LABELS,
            categories=sorted({product.category for product in products if product.category}),
            repository_url="https://github.com/ozcanr17/firsat_radar",
        ),
        encoding="utf-8",
    )
    (output_directory / ".nojekyll").write_text("", encoding="utf-8")
    return StaticExportResult(
        output_path=output_path,
        products=len(products),
        recommendations=len(recommendations),
    )
