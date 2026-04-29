import asyncio

from src.domain.models.trend_daily_report import TrendDailyReport
from src.domain.models.trend_keyword import TrendKeywordCreate
from src.domain.models.trend_snapshot import TrendSnapshotCreate
from src.services.trend_daily_report_service import TrendDailyReportService
from src.services.trend_keyword_service import TrendKeywordService
from src.services.trend_snapshot_service import TrendSnapshotService


class FakeReviewer:
    def __init__(self):
        self.calls = []

    async def review(self, opportunities):
        self.calls.append(opportunities)
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
                    "risks": ["需要保证教程能跑通"],
                    "next_action": "建议今天查看。",
                }
            ],
        }


class FakeNotifier:
    def __init__(self, *, success=True):
        self.success = success
        self.messages = []

    async def send(self, title, body):
        self.messages.append((title, body))
        return {
            "channel": "bark",
            "success": self.success,
            "message": "发送成功" if self.success else "Bark 未配置",
        }


def _seed_snapshot(db_path: str):
    keyword_service = TrendKeywordService(db_path=db_path)
    snapshot_service = TrendSnapshotService(db_path=db_path)
    keyword = asyncio.run(
        keyword_service.create_keyword(
            TrendKeywordCreate(keyword="AI商品图工作流", category="AI")
        )
    )
    return asyncio.run(
        snapshot_service.create_snapshot(
            TrendSnapshotCreate(
                keyword_id=keyword.id,
                total_results=10,
                items=[
                    {
                        "title": "AI商品图 ComfyUI 工作流",
                        "price": "59",
                        "seller_nickname": "A店",
                        "want_count": "20",
                        "publish_time": "1小时前",
                        "link": "https://example.com/a",
                    },
                    {
                        "title": "电商主图工作流资料包",
                        "price": "79",
                        "seller_nickname": "B店",
                        "want_count": "16",
                        "publish_time": "今天",
                        "link": "https://example.com/b",
                    },
                    {
                        "title": "AI商品图提示词教程",
                        "price": "69",
                        "seller_nickname": "C店",
                        "want_count": "10",
                        "publish_time": "昨天",
                        "link": "https://example.com/c",
                    },
                ],
            )
        )
    )


def test_daily_report_service_runs_ai_review_and_sends_notification(tmp_path):
    db_path = str(tmp_path / "app.sqlite3")
    _seed_snapshot(db_path)
    reviewer = FakeReviewer()
    notifier = FakeNotifier()
    service = TrendDailyReportService(
        db_path=db_path,
        ai_reviewer=reviewer,
        notifier=notifier,
    )

    report = asyncio.run(service.run_report(candidate_limit=5, push=True))

    assert isinstance(report, TrendDailyReport)
    assert report.status == "completed"
    assert report.push_status == "sent"
    assert report.candidate_snapshot_ids
    assert report.ai_review["daily_summary"] == "今天优先看 AI 商品图方向。"
    assert "AI商品图工作流" in report.push_body
    assert notifier.messages[0][0] == "闲鱼 AI 机会日报"
    assert reviewer.calls and reviewer.calls[0][0].keyword == "AI商品图工作流"

    latest = asyncio.run(service.get_latest_report())
    assert latest is not None
    assert latest.id == report.id


def test_daily_report_service_records_failed_push(tmp_path):
    db_path = str(tmp_path / "app.sqlite3")
    _seed_snapshot(db_path)
    service = TrendDailyReportService(
        db_path=db_path,
        ai_reviewer=FakeReviewer(),
        notifier=FakeNotifier(success=False),
    )

    report = asyncio.run(service.run_report(candidate_limit=5, push=True))

    assert report.push_status == "failed"
    assert "Bark 未配置" in report.error_message


def test_daily_report_service_handles_empty_opportunities(tmp_path):
    service = TrendDailyReportService(
        db_path=str(tmp_path / "app.sqlite3"),
        ai_reviewer=FakeReviewer(),
        notifier=FakeNotifier(),
    )

    report = asyncio.run(service.run_report(push=False))

    assert report.push_status == "skipped"
    assert report.ai_review["items"] == []
    assert "暂无明显机会" in report.push_body
