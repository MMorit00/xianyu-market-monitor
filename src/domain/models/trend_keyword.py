"""
闲鱼站内趋势关键词模型。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


def _normalize_optional_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_keyword(value) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("关键词不能为空。")
    return text


class TrendKeyword(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    keyword: str
    category: str = ""
    enabled: bool = True
    notes: str = ""
    created_at: datetime
    updated_at: datetime


class TrendKeywordCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keyword: str
    category: str = ""
    enabled: bool = True
    notes: str = ""

    @field_validator("keyword", mode="before")
    @classmethod
    def normalize_keyword(cls, value):
        return _normalize_keyword(value)

    @field_validator("category", "notes", mode="before")
    @classmethod
    def normalize_text(cls, value):
        return _normalize_optional_text(value)


class TrendKeywordUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keyword: Optional[str] = None
    category: Optional[str] = None
    enabled: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("keyword", mode="before")
    @classmethod
    def normalize_keyword(cls, value):
        if value is None:
            return None
        return _normalize_keyword(value)

    @field_validator("category", "notes", mode="before")
    @classmethod
    def normalize_text(cls, value):
        if value is None:
            return None
        return _normalize_optional_text(value)
