"""
闲鱼站内趋势快照模型。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


COUNT_WAN_PATTERN = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*万\s*$")
NUMBER_PATTERN = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")


def _normalize_optional_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_optional_keyword(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_text_list(values) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]
    normalized = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _parse_optional_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "")
    match = NUMBER_PATTERN.search(text)
    if not match:
        return None
    return float(match.group(0))


def _parse_int(value) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    text = str(value).replace(",", "").strip()
    wan_match = COUNT_WAN_PATTERN.match(text)
    if wan_match:
        return max(int(float(wan_match.group(1)) * 10000), 0)
    match = NUMBER_PATTERN.search(text)
    if not match:
        return 0
    return max(int(float(match.group(0))), 0)


def _parse_optional_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    return _parse_int(value)


def _parse_optional_datetime(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


class TrendItemSample(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_id: str = ""
    title: str = ""
    price: Optional[float] = None
    price_display: str = ""
    seller_nickname: str = ""
    want_count: int = 0
    publish_time: str = ""
    link: str = ""
    image_key: str = ""
    raw_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "item_id",
        "title",
        "price_display",
        "seller_nickname",
        "publish_time",
        "link",
        "image_key",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        return _normalize_optional_text(value)

    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, value):
        return _parse_optional_float(value)

    @field_validator("want_count", mode="before")
    @classmethod
    def normalize_count(cls, value):
        return _parse_int(value)


class TrendSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keyword_id: Optional[int] = None
    keyword: Optional[str] = None
    category: str = ""
    snapshot_time: Optional[datetime] = None
    total_results: Optional[int] = None
    new_items_24h: Optional[int] = None
    new_items_3d: Optional[int] = None
    seller_count: Optional[int] = None
    new_seller_count: Optional[int] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    median_price: Optional[float] = None
    want_count_total: Optional[int] = None
    want_count_avg: Optional[float] = None
    title_terms: Optional[list[str]] = None
    title_repetition_rate: Optional[float] = None
    same_image_count: Optional[int] = None
    low_price_item_ratio: Optional[float] = None
    execution_score: Optional[float] = None
    raw_metrics: dict[str, Any] = Field(default_factory=dict)
    items: list[TrendItemSample] = Field(default_factory=list)

    @field_validator("keyword", mode="before")
    @classmethod
    def normalize_keyword(cls, value):
        return _normalize_optional_keyword(value)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value):
        return _normalize_optional_text(value)

    @field_validator("snapshot_time", mode="before")
    @classmethod
    def normalize_snapshot_time(cls, value):
        return _parse_optional_datetime(value)

    @field_validator(
        "total_results",
        "new_items_24h",
        "new_items_3d",
        "seller_count",
        "new_seller_count",
        "want_count_total",
        "same_image_count",
        mode="before",
    )
    @classmethod
    def normalize_optional_int(cls, value):
        return _parse_optional_int(value)

    @field_validator(
        "min_price",
        "max_price",
        "median_price",
        "want_count_avg",
        "title_repetition_rate",
        "low_price_item_ratio",
        "execution_score",
        mode="before",
    )
    @classmethod
    def normalize_optional_float(cls, value):
        return _parse_optional_float(value)

    @field_validator("title_terms", mode="before")
    @classmethod
    def normalize_terms(cls, value):
        if value is None:
            return None
        return _normalize_text_list(value)


class TrendSnapshotRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    limit_per_keyword: int = 40

    @field_validator("limit_per_keyword", mode="before")
    @classmethod
    def normalize_limit(cls, value):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 40
        return max(1, min(parsed, 100))


class TrendSnapshotItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    snapshot_id: int
    item_id: str = ""
    title: str = ""
    price: Optional[float] = None
    price_display: str = ""
    seller_nickname: str = ""
    want_count: int = 0
    publish_time: str = ""
    link: str = ""
    image_key: str = ""
    raw_json: dict[str, Any] = Field(default_factory=dict)


class TrendSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    keyword_id: Optional[int] = None
    keyword: str
    category: str = ""
    snapshot_time: datetime
    total_results: int = 0
    new_items_24h: int = 0
    new_items_3d: int = 0
    seller_count: int = 0
    new_seller_count: int = 0
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    median_price: Optional[float] = None
    want_count_total: int = 0
    want_count_avg: float = 0
    title_terms: list[str] = Field(default_factory=list)
    title_repetition_rate: float = 0
    same_image_count: int = 0
    low_price_item_ratio: float = 0
    opportunity_score: float = 0
    opportunity_level: str = "D"
    growth_score: float = 0
    competition_score: float = 0
    profit_score: float = 0
    freshness_score: float = 0
    execution_score: float = 0
    reasons: list[str] = Field(default_factory=list)
    action: str = ""
    raw_metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TrendSnapshotDetail(TrendSnapshot):
    items: list[TrendSnapshotItem] = Field(default_factory=list)


class TrendOpportunity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    snapshot_id: int
    keyword_id: Optional[int] = None
    keyword: str
    category: str = ""
    snapshot_time: datetime
    opportunity_score: float
    opportunity_level: str
    growth_score: float
    competition_score: float
    profit_score: float
    freshness_score: float
    execution_score: float
    reasons: list[str] = Field(default_factory=list)
    action: str = ""
