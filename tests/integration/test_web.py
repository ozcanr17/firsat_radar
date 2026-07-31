import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_reports_ready_database(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "last_run_at": None,
    }


@pytest.mark.asyncio
async def test_dashboard_has_explicit_empty_state(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "NO_DATA" in response.text
    assert "örnek veya sahte pazar verisi göstermez" in response.text
