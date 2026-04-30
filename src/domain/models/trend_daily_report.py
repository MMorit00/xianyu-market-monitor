"""
闲鱼机会日报模型。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


class TrendDailyReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    report_date: str
    status: str
    candidate_snapshot_ids: list[int] = Field(default_factory=list)
    ai_review: dict[str, Any] = Field(default_factory=dict)
    push_title: str = ""
    push_body: str = ""
    push_channel: str = "bark"
    push_status: str = "pending"
    error_message: str = ""
    created_at: datetime
    sent_at: datetime | None = None


class TrendDailyReportRunRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidate_limit: int = 10
    push: bool = True
    refresh_snapshots: bool = True

    @field_validator("candidate_limit", mode="before")
    @classmethod
    def normalize_candidate_limit(cls, value):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 10
        return max(1, min(parsed, 20))


class TrendDailyReportTestNotificationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = "闲鱼 AI 机会日报测试"
    body: str = "这是一条 Bark 日报测试通知。"

    @field_validator("title", "body", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return _normalize_text(value)
