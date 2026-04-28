from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.routes import trends
from src.services.trend_keyword_service import TrendKeywordService


def _build_client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(trends.router)
    service = TrendKeywordService(db_path=str(tmp_path / "app.sqlite3"))
    app.dependency_overrides[deps.get_trend_keyword_service] = lambda: service
    return TestClient(app)


def test_trend_keyword_api_crud_and_filters(tmp_path):
    client = _build_client(tmp_path)

    response = client.post(
        "/api/trends/keywords",
        json={
            "keyword": "ComfyUI 工作流",
            "category": "AI",
            "notes": "重点观察",
        },
    )
    assert response.status_code == 200
    created = response.json()["item"]
    assert created["keyword"] == "ComfyUI 工作流"
    assert created["enabled"] is True

    duplicate = client.post(
        "/api/trends/keywords",
        json={"keyword": "ComfyUI 工作流"},
    )
    assert duplicate.status_code == 409

    response = client.get("/api/trends/keywords")
    assert response.status_code == 200
    assert [item["keyword"] for item in response.json()["items"]] == ["ComfyUI 工作流"]

    response = client.patch(
        f"/api/trends/keywords/{created['id']}",
        json={"enabled": False, "notes": "暂停"},
    )
    assert response.status_code == 200
    assert response.json()["item"]["enabled"] is False

    response = client.get("/api/trends/keywords")
    assert response.status_code == 200
    assert response.json()["items"] == []

    response = client.get("/api/trends/keywords?include_disabled=true")
    assert response.status_code == 200
    assert [item["keyword"] for item in response.json()["items"]] == ["ComfyUI 工作流"]

    response = client.delete(f"/api/trends/keywords/{created['id']}")
    assert response.status_code == 200

    response = client.get(f"/api/trends/keywords/{created['id']}")
    assert response.status_code == 404


def test_trend_keyword_api_rejects_blank_keyword(tmp_path):
    client = _build_client(tmp_path)

    response = client.post("/api/trends/keywords", json={"keyword": " "})

    assert response.status_code == 422
