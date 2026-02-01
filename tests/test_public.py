import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from api.public import router as public_router
from api.health import router as health_router


@pytest.fixture
def client():
    # Create a test app without middleware
    test_app = FastAPI()
    test_app.include_router(public_router)
    test_app.include_router(health_router)
    return TestClient(test_app)


def test_search_profiles_empty(client):
    """Test public search endpoint with no results."""
    response = client.get("/search?q=nonexistent")
    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_get_profile_not_found(client):
    """Test public profile view endpoint with invalid ID."""
    response = client.get("/profiles/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    # Since no DB, it should return unhealthy
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "uptime_seconds" in data