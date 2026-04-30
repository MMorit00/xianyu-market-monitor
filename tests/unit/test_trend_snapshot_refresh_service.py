import asyncio

from src.domain.models.trend_keyword import TrendKeywordCreate
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.services.result_storage_service import save_result_record
from src.services.trend_keyword_service import TrendKeywordService
from src.services.trend_snapshot_refresh_service import TrendSnapshotRefreshService


def test_refresh_service_creates_snapshot_from_result_items(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_path = str(tmp_path / "app.sqlite3")
    monkeypatch.setenv("APP_DATABASE_FILE", db_path)
    bootstrap_sqlite_storage(legacy_config_file=None)
    keyword_service = TrendKeywordService()
    asyncio.run(
        keyword_service.create_keyword(
            TrendKeywordCreate(keyword="AI商品图", category="AI")
        )
    )

    records = [
        {
            "爬取时间": "2026-04-30T09:00:00",
            "搜索关键字": "AI商品图",
            "任务名称": "AI商品图",
            "商品信息": {
                "商品ID": "1",
                "商品标题": "AI商品图工作流",
                "商品链接": "https://www.goofish.com/item?id=1",
                "当前售价": "¥59",
                "发布时间": "今天",
                "“想要”人数": "18",
                "卖家昵称": "A店",
            },
        },
        {
            "爬取时间": "2026-04-30T09:01:00",
            "搜索关键字": "AI商品图",
            "任务名称": "AI商品图",
            "商品信息": {
                "商品ID": "2",
                "商品标题": "电商主图提示词模板",
                "商品链接": "https://www.goofish.com/item?id=2",
                "当前售价": "¥79",
                "发布时间": "昨天",
                "“想要”人数": "12",
                "卖家昵称": "B店",
            },
        },
    ]
    for record in records:
        asyncio.run(save_result_record(record, keyword="AI商品图"))

    service = TrendSnapshotRefreshService()
    result = asyncio.run(service.refresh_enabled_keywords(limit_per_keyword=10))

    assert result["created_count"] == 1
    snapshot = result["items"][0]
    assert snapshot["keyword"] == "AI商品图"
    assert snapshot["total_results"] == 2
    assert snapshot["new_items_24h"] >= 1
    assert snapshot["seller_count"] == 2
    assert snapshot["want_count_total"] == 30
    assert snapshot["median_price"] == 69
    assert snapshot["items"][0]["title"] == "电商主图提示词模板"


def test_refresh_service_skips_keywords_without_results(tmp_path):
    db_path = str(tmp_path / "app.sqlite3")
    keyword_service = TrendKeywordService(db_path=db_path)
    keyword = asyncio.run(
        keyword_service.create_keyword(TrendKeywordCreate(keyword="ComfyUI"))
    )
    service = TrendSnapshotRefreshService(db_path=db_path)

    result = asyncio.run(service.refresh_enabled_keywords())

    assert result["created_count"] == 0
    assert result["skipped"] == [{"keyword_id": keyword.id, "keyword": "ComfyUI"}]
