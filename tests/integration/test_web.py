from pathlib import Path

import pytest
from httpx import AsyncClient
from typer.testing import CliRunner

from app.cli import app
from app.config import Settings
from app.db.migrations import upgrade_database
from app.services.static_site import export_static_site


@pytest.mark.asyncio
async def test_health_endpoint_reports_ready_database(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "last_run_at": None,
        "scheduler_status": "idle",
        "consecutive_failures": 0,
        "circuit_open_until": None,
        "last_backup_at": None,
    }


@pytest.mark.asyncio
async def test_dashboard_has_explicit_empty_state(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "NO_DATA" in response.text
    assert "örnek veya sahte pazar verisi göstermez" in response.text


@pytest.mark.asyncio
async def test_products_api_has_empty_live_state(client: AsyncClient) -> None:
    response = await client.get("/api/v1/products")

    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0}


@pytest.mark.asyncio
async def test_opportunities_api_has_empty_live_state(client: AsyncClient) -> None:
    response = await client.get("/api/v1/opportunities")

    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0}


@pytest.mark.asyncio
async def test_product_search_and_recommendations_have_empty_state(
    client: AsyncClient,
) -> None:
    products = await client.get(
        "/products",
        params={"q": "telefon", "category": "Telefon", "sort": "price_asc"},
    )
    recommendations = await client.get("/recommendations", params={"route": "resale"})

    assert products.status_code == 200
    assert "Eşleşen ürün bulunamadı" in products.text
    assert recommendations.status_code == 200
    assert "Bu filtrede öneri yok" in recommendations.text


@pytest.mark.asyncio
async def test_trade_desk_and_watchlist_api(client: AsyncClient) -> None:
    page = await client.get("/trade-desk")
    created = await client.post(
        "/api/v1/watchlist",
        json={
            "target_type": "product",
            "label": "Takip edilecek bebek arabası",
            "source_url": "https://www.hepsiburada.com/ornek-p-HBCV123?magaza=x",
            "priority": 5,
            "refresh_interval_hours": 12,
        },
    )
    listed = await client.get("/api/v1/watchlist")
    deleted = await client.delete(f"/api/v1/watchlist/{created.json()['id']}")

    assert page.status_code == 200
    assert "Esnaf masası" in page.text
    assert "İzleme kuyruğu boş" in page.text
    assert created.status_code == 201
    assert created.json()["source_url"] == "https://www.hepsiburada.com/ornek-p-HBCV123"
    assert created.json()["refresh_due"] is True
    assert listed.json()["count"] == 1
    assert deleted.status_code == 204


def test_direct_index_is_a_static_launcher() -> None:
    launcher = (Path(__file__).parents[2] / "app" / "web" / "templates" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "PANEL BAŞLATICI" in launcher
    assert "open-panel" in launcher
    assert "{{" not in launcher
    assert "{%" not in launcher


def test_open_panel_command_is_available() -> None:
    result = CliRunner().invoke(app, ["open-panel", "--help"])

    assert result.exit_code == 0


def test_static_site_export_has_safe_empty_state(settings: Settings, tmp_path: Path) -> None:
    upgrade_database(settings)
    result = export_static_site(settings, tmp_path / "public")
    html = result.output_path.read_text(encoding="utf-8")

    assert result.products == 0
    assert result.recommendations == 0
    assert "PazarRadar" in html
    assert "Henüz yayımlanabilir öneri yok" in html
    assert "kâr, satış veya üretim başarısı garantisi vermez" in html
    assert "Hızlı kârlılık testi" in html
    assert (tmp_path / "public" / ".nojekyll").exists()
