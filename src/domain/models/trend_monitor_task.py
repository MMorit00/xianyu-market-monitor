"""
趋势关键词监控任务同步模型。
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.cron_utils import validate_cron_expression


def _normalize_optional_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class TrendMonitorTaskSyncRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cron: Optional[str] = "0 */6 * * *"
    max_pages: int = Field(default=2, ge=1, le=10)
    personal_only: bool = True
    free_shipping: bool = False
    new_publish_option: Optional[str] = "3天内"
    region: Optional[str] = None
    min_price: Optional[str] = None
    max_price: Optional[str] = None
    enabled: bool = True
    update_existing: bool = True

    @field_validator("cron", mode="before")
    @classmethod
    def normalize_cron(cls, value):
        return _normalize_optional_text(value)

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value):
        return validate_cron_expression(value)

    @field_validator("new_publish_option", "region", "min_price", "max_price", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return _normalize_optional_text(value)
