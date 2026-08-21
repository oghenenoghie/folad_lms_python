import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fastapi_app"))

from main import app  # noqa: E402

client = TestClient(app)


def test_health_ok():
    response = client.get("/edge/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


def test_ready_ok():
    """Requires Postgres + Redis reachable at the configured defaults (see Docker Compose)."""
    response = client.get("/edge/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["checks"] == {"database": True, "cache": True}
