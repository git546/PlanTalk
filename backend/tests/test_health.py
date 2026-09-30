from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "PlanTalk API",
        "environment": "development",
    }


def test_root_links() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["health"] == "/api/health"
