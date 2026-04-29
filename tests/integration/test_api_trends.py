from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.routes import trends
from src.services.trend_keyword_service import TrendKeywordService
from src.services.trend_snapshot_service import TrendSnapshotService


def _build_client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(trends.router)
    db_path = str(tmp_path / "app.sqlite3")
    keyword_service = TrendKeywordService(db_path=db_path)
    snapshot_service = TrendSnapshotService(db_path=db_path)
    app.dependency_overrides[deps.get_trend_keyword_service] = lambda: keyword_service
    app.dependency_overrides[deps.get_trend_snapshot_service] = lambda: snapshot_service
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


def test_trend_snapshot_api_creates_snapshot_and_lists_opportunities(tmp_path):
    client = _build_client(tmp_path)

    response = client.post(
        "/api/trends/keywords",
        json={"keyword": "ComfyUI 工作流", "category": "AI"},
    )
    assert response.status_code == 200
    keyword = response.json()["item"]

    response = client.post(
        "/api/trends/snapshots",
        json={
            "keyword_id": keyword["id"],
            "total_results": 10,
            "items": [
                {
                    "title": "ComfyUI 工作流资料包",
                    "price": "59",
                    "seller_nickname": "A店",
                    "want_count": "20",
                    "publish_time": "1小时前",
                    "link": "https://example.com/a",
                },
                {
                    "title": "ComfyUI 工作流教程",
                    "price": "79",
                    "seller_nickname": "B店",
                    "want_count": "12",
                    "publish_time": "今天",
                    "link": "https://example.com/b",
                },
                {
                    "title": "AI绘画工作流整合包",
                    "price": "69",
                    "seller_nickname": "C店",
                    "want_count": "8",
                    "publish_time": "昨天",
                    "link": "https://example.com/c",
                },
            ],
        },
    )
    assert response.status_code == 200
    snapshot = response.json()["item"]
    assert snapshot["keyword"] == "ComfyUI 工作流"
    assert snapshot["new_items_24h"] == 2
    assert snapshot["seller_count"] == 3
    assert snapshot["opportunity_level"] in {"A", "B"}
    assert len(snapshot["items"]) == 3

    response = client.get("/api/trends/snapshots")
    assert response.status_code == 200
    assert [item["keyword"] for item in response.json()["items"]] == ["ComfyUI 工作流"]

    response = client.get(f"/api/trends/snapshots/{snapshot['id']}?include_items=true")
    assert response.status_code == 200
    assert len(response.json()["item"]["items"]) == 3

    response = client.get("/api/trends/opportunities")
    assert response.status_code == 200
    opportunities = response.json()["items"]
    assert len(opportunities) == 1
    assert opportunities[0]["keyword"] == "ComfyUI 工作流"
