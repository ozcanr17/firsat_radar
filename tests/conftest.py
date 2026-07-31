from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.db.migrations import upgrade_database
from app.db.session import SessionFactory, build_engine, build_session_factory
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(environment="test", data_dir=tmp_path)


@pytest.fixture
def session_factory(settings: Settings) -> Iterator[SessionFactory]:
    upgrade_database(settings)
    engine = build_engine(settings)
    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


@pytest_asyncio.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    upgrade_database(settings)
    application = create_app(settings)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    application.state.engine.dispose()
