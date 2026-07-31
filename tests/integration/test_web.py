from pathlib import Path

import pytest
from httpx import AsyncClient
from typer.testing import CliRunner

from app.cli import app


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
