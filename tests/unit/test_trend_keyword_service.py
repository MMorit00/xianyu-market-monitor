import asyncio

import pytest

from src.domain.models.trend_keyword import TrendKeywordCreate, TrendKeywordUpdate
from src.services.trend_keyword_service import (
    TrendKeywordConflictError,
    TrendKeywordService,
)


def test_trend_keyword_service_crud(tmp_path):
    service = TrendKeywordService(db_path=str(tmp_path / "app.sqlite3"))

    created = asyncio.run(
        service.create_keyword(
            TrendKeywordCreate(
                keyword=" ComfyUI 工作流 ",
                category="AI",
                notes="站内追新",
            )
        )
    )

    assert created.id == 1
    assert created.keyword == "ComfyUI 工作流"
    assert created.category == "AI"
    assert created.enabled is True

    items = asyncio.run(service.list_keywords())
    assert [item.keyword for item in items] == ["ComfyUI 工作流"]

    updated = asyncio.run(
        service.update_keyword(
            created.id,
            TrendKeywordUpdate(enabled=False, notes="暂停观察"),
        )
    )
    assert updated is not None
    assert updated.enabled is False
    assert updated.notes == "暂停观察"

    enabled_items = asyncio.run(service.list_keywords())
    assert enabled_items == []

    all_items = asyncio.run(service.list_keywords(include_disabled=True))
    assert [item.keyword for item in all_items] == ["ComfyUI 工作流"]

    assert asyncio.run(service.delete_keyword(created.id)) is True
    assert asyncio.run(service.get_keyword(created.id)) is None


def test_trend_keyword_service_rejects_duplicate_keyword(tmp_path):
    service = TrendKeywordService(db_path=str(tmp_path / "app.sqlite3"))
    payload = TrendKeywordCreate(keyword="AI课程")

    asyncio.run(service.create_keyword(payload))

    with pytest.raises(TrendKeywordConflictError):
        asyncio.run(service.create_keyword(payload))


def test_trend_keyword_update_missing_returns_none(tmp_path):
    service = TrendKeywordService(db_path=str(tmp_path / "app.sqlite3"))

    result = asyncio.run(
        service.update_keyword(404, TrendKeywordUpdate(category="AI"))
    )

    assert result is None
