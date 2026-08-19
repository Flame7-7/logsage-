"""
Integration tests for the ingestion and incident endpoints.
Requires a running test database + Redis.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

# These tests use pytest-asyncio and httpx for async HTTP testing.
# Run with: pytest tests/integration/ -v

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sample_txt_log():
    return b"""2024-01-15 12:01:00 ERROR redis: Redis connection timeout after 5000ms
2024-01-15 12:01:05 WARNING gateway: Shard [3] heartbeat timeout
2024-01-15 12:01:10 ERROR redis: Redis pool exhausted: all 50 connections in use
2024-01-15 12:01:15 CRITICAL worker: All workers unresponsive
2024-01-15 12:01:20 ERROR gateway: WebSocket connection closed unexpectedly
2024-01-15 12:01:25 INFO redis: Redis connection restored
"""


@pytest.fixture
def sample_json_log():
    lines = [
        '{"timestamp":"2024-01-15T12:01:00","level":"ERROR","service":"redis","message":"Connection timeout"}',
        '{"timestamp":"2024-01-15T12:01:05","level":"ERROR","service":"gateway","message":"Reconnect spike"}',
        '{"timestamp":"2024-01-15T12:01:10","level":"CRITICAL","service":"db","message":"Pool exhausted"}',
    ]
    return "\n".join(lines).encode()


class TestLogUpload:
    """Tests for POST /api/v1/logs/upload"""

    async def test_upload_txt_success(self, async_client, sample_txt_log):
        response = await async_client.post(
            "/api/v1/logs/upload",
            files={"file": ("test.log", sample_txt_log, "text/plain")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["processed_lines"] > 0
        assert "session_id" in data

    async def test_upload_json_success(self, async_client, sample_json_log):
        response = await async_client.post(
            "/api/v1/logs/upload",
            files={"file": ("test.json", sample_json_log, "application/json")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["processed_lines"] == 3

    async def test_upload_empty_file(self, async_client):
        response = await async_client.post(
            "/api/v1/logs/upload",
            files={"file": ("empty.log", b"", "text/plain")},
        )
        assert response.status_code == 400

    async def test_upload_no_file(self, async_client):
        response = await async_client.post("/api/v1/logs/upload")
        assert response.status_code == 422


class TestSimulate:
    """Tests for POST /api/v1/logs/simulate"""

    async def test_simulate_default(self, async_client):
        response = await async_client.post("/api/v1/logs/simulate?count=50")
        assert response.status_code == 201
        data = response.json()
        assert data["processed_lines"] == 50

    async def test_simulate_incident_scenario(self, async_client):
        response = await async_client.post(
            "/api/v1/logs/simulate?count=100&scenario=incident"
        )
        assert response.status_code == 201

    async def test_simulate_count_too_low(self, async_client):
        response = await async_client.post("/api/v1/logs/simulate?count=5")
        assert response.status_code == 422


class TestIncidents:
    """Tests for GET /api/v1/incidents"""

    async def test_list_incidents_empty(self, async_client):
        response = await async_client.get("/api/v1/incidents")
        assert response.status_code == 200
        data = response.json()
        assert "incidents" in data
        assert "total" in data

    async def test_list_incidents_filter_status(self, async_client):
        response = await async_client.get("/api/v1/incidents?status=open")
        assert response.status_code == 200

    async def test_get_nonexistent_incident(self, async_client):
        response = await async_client.get("/api/v1/incidents/nonexistent-id")
        assert response.status_code == 404


class TestClusters:
    """Tests for GET /api/v1/clusters"""

    async def test_list_clusters(self, async_client):
        response = await async_client.get("/api/v1/clusters")
        assert response.status_code == 200
        data = response.json()
        assert "clusters" in data


class TestMetrics:
    """Tests for GET /api/v1/metrics"""

    async def test_get_metrics(self, async_client):
        response = await async_client.get("/api/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "events_per_second" in data
        assert "incident_count" in data


class TestHealth:
    async def test_health_check(self, async_client):
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
