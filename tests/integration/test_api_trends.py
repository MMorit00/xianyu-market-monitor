from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.routes import trends
from src.services.trend_daily_report_service import TrendDailyReportService
from src.services.trend_keyword_service import TrendKeywordService
from src.services.trend_snapshot_service import TrendSnapshotService


class FakeReviewer:
    async def review(self, opportunities):
        if not opportunities:
            return {"daily_summary": "今日暂无明显机会。", "items": []}
        return {
            "daily_summary": "今天优先看 AI 商品图方向。",
            "items": [
                {
                    "snapshot_id": opportunities[0].snapshot_id,
                    "keyword": opportunities[0].keyword,
                    "rank": "A",
                    "should_push": True,
                    "why": "上新快，卖家少。",
                    "sell_angle": "资料包 + 新手教程。",
                    "advantages": ["标准化交付"],
                    "risks": ["教程需要跑通"],
                    "next_action": "建议今天查看。",
                }
            ],
        }


class FakeNotifier:
    def __init__(self):
        self.messages = []

    async def send(self, title, body):
        self.messages.append((title, body))
        return {"channel": "bark", "success": True, "message": "发送成功"}


def _build_client(tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(trends.router)
    db_path = str(tmp_path / "app.sqlite3")
    keyword_service = TrendKeywordService(db_path=db_path)
    snapshot_service = TrendSnapshotService(db_path=db_path)
    notifier = FakeNotifier()
    daily_report_service = TrendDailyReportService(
        db_path=db_path,
        ai_reviewer=FakeReviewer(),
        notifier=notifier,
    )
    app.dependency_overrides[deps.get_trend_keyword_service] = lambda: keyword_service
    app.dependency_overrides[deps.get_trend_snapshot_service] = lambda: snapshot_service
    app.dependency_overrides[deps.get_trend_daily_report_service] = (
        lambda: daily_report_service
    )
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


def test_trend_daily_report_api_runs_and_returns_latest(tmp_path):
    client = _build_client(tmp_path)

    response = client.post(
        "/api/trends/snapshots",
        json={
            "keyword": "AI商品图工作流",
            "category": "AI",
            "total_results": 10,
            "items": [
                {
                    "title": "AI商品图工作流",
                    "price": "59",
                    "seller_nickname": "A店",
                    "want_count": "18",
                    "publish_time": "1小时前",
                    "link": "https://example.com/a",
                },
                {
                    "title": "电商主图提示词模板",
                    "price": "79",
                    "seller_nickname": "B店",
                    "want_count": "12",
                    "publish_time": "今天",
                    "link": "https://example.com/b",
                },
            ],
        },
    )
    assert response.status_code == 200

    response = client.post(
        "/api/trends/daily-report/run",
        json={"candidate_limit": 5, "push": True},
    )
    assert response.status_code == 200
    report = response.json()["item"]
    assert report["push_status"] == "sent"
    assert report["ai_review"]["daily_summary"] == "今天优先看 AI 商品图方向。"
    assert "AI商品图工作流" in report["push_body"]

    response = client.get("/api/trends/daily-report/latest")
    assert response.status_code == 200
    assert response.json()["item"]["id"] == report["id"]


def test_trend_daily_report_api_sends_test_notification(tmp_path):
    client = _build_client(tmp_path)

    response = client.post(
        "/api/trends/daily-report/send-test",
        json={"title": "测试标题", "body": "测试内容"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["success"] is True
