import asyncio

import pytest

from src.domain.models.trend_keyword import TrendKeywordCreate
from src.domain.models.trend_snapshot import TrendSnapshotCreate
from src.services.trend_keyword_service import TrendKeywordService
from src.services.trend_snapshot_service import (
    TrendSnapshotService,
    TrendSnapshotValidationError,
)


def test_trend_snapshot_service_creates_snapshot_and_scores_opportunity(tmp_path):
    db_path = str(tmp_path / "app.sqlite3")
    keyword_service = TrendKeywordService(db_path=db_path)
    snapshot_service = TrendSnapshotService(db_path=db_path)
    keyword = asyncio.run(
        keyword_service.create_keyword(
            TrendKeywordCreate(keyword="ComfyUI 工作流", category="AI")
        )
    )

    snapshot = asyncio.run(
        snapshot_service.create_snapshot(
            TrendSnapshotCreate(
                keyword_id=keyword.id,
                total_results=12,
                items=[
                    {
                        "item_id": "1",
                        "title": "ComfyUI 工作流 AI绘画资料包",
                        "price": "59",
                        "seller_nickname": "A店",
                        "want_count": "24",
                        "publish_time": "2小时前",
                        "link": "https://example.com/1",
                        "image_key": "img-a",
                    },
                    {
                        "item_id": "2",
                        "title": "ComfyUI 零基础工作流教程",
                        "price": "69",
                        "seller_nickname": "B店",
                        "want_count": "18",
                        "publish_time": "今天",
                        "link": "https://example.com/2",
                        "image_key": "img-a",
                    },
                    {
                        "item_id": "3",
                        "title": "AI绘画工作流整合包",
                        "price": "89",
                        "seller_nickname": "C店",
                        "want_count": "12",
                        "publish_time": "昨天",
                        "link": "https://example.com/3",
                        "image_key": "img-c",
                    },
                    {
                        "item_id": "4",
                        "title": "ComfyUI 提示词和工作流",
                        "price": "49",
                        "seller_nickname": "A店",
                        "want_count": "9",
                        "publish_time": "2天前",
                        "link": "https://example.com/4",
                        "image_key": "img-d",
                    },
                ],
            )
        )
    )

    assert snapshot.keyword == "ComfyUI 工作流"
    assert snapshot.category == "AI"
    assert snapshot.total_results == 12
    assert snapshot.new_items_24h == 2
    assert snapshot.new_items_3d == 4
    assert snapshot.seller_count == 3
    assert snapshot.median_price == 64
    assert snapshot.want_count_total == 63
    assert snapshot.same_image_count == 1
    assert snapshot.opportunity_level == "A"
    assert snapshot.opportunity_score >= 75
    assert len(snapshot.items) == 4

    opportunities = asyncio.run(snapshot_service.list_opportunities())
    assert len(opportunities) == 1
    assert opportunities[0].keyword == "ComfyUI 工作流"
    assert opportunities[0].opportunity_level == "A"


def test_trend_snapshot_service_supports_manual_metrics_without_keyword_pool(tmp_path):
    service = TrendSnapshotService(db_path=str(tmp_path / "app.sqlite3"))

    snapshot = asyncio.run(
        service.create_snapshot(
            TrendSnapshotCreate(
                keyword="副业资料包",
                category="资料",
                total_results=80,
                new_items_24h=1,
                new_items_3d=4,
                seller_count=45,
                median_price=19.9,
                want_count_avg=3,
                title_repetition_rate=0.5,
                low_price_item_ratio=0.35,
            )
        )
    )

    assert snapshot.keyword == "副业资料包"
    assert snapshot.items == []
    assert snapshot.competition_score < 50
    assert snapshot.opportunity_level in {"C", "D"}


def test_trend_snapshot_service_rejects_missing_keyword(tmp_path):
    service = TrendSnapshotService(db_path=str(tmp_path / "app.sqlite3"))

    with pytest.raises(TrendSnapshotValidationError):
        asyncio.run(service.create_snapshot(TrendSnapshotCreate()))
