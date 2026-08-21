import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


def test_health_ok(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


@pytest.mark.django_db
def test_ready_ok(client):
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["checks"] == {"database": True, "cache": True}
