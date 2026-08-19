"""
LogSage AI — Test Configuration
"""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_client():
    """
    Provides an async HTTP test client.
    In real tests, this would use a test DB + mocked Redis.
    For CI, set TEST_DATABASE_URL and TEST_REDIS_URL env vars.
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

    from main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
