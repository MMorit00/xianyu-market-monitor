"""
从已有监控结果刷新趋势快照。
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone

from src.domain.models.trend_snapshot import TrendItemSample, TrendSnapshotCreate
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services.price_history_service import parse_price_value
from src.services.trend_keyword_service import TrendKeywordService
from src.services.trend_snapshot_service import TrendSnapshotService


COUNT_WAN_PATTERN = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*万\s*$")
NUMBER_PATTERN = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")


def _parse_count(value) -> int:
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


def _parse_publish_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text or text == "未知时间":
        return None
    now = datetime.now(timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    if any(marker in text for marker in ("刚刚", "分钟前", "小时前", "今天")):
        return now
    if "昨天" in text:
        return now - timedelta(days=1)
    if "前天" in text:
        return now - timedelta(days=2)
    day_match = re.search(r"([0-9]+)\s*天前", text)
    if day_match:
        return now - timedelta(days=int(day_match.group(1)))
    return None


def _row_to_item_sample(row) -> TrendItemSample:
    return TrendItemSample(
        item_id=row["item_id"] or "",
        title=row["title"] or "",
        price=row["price"],
        price_display=row["price_display"] or "",
        seller_nickname=row["seller_nickname"] or "",
        want_count=0,
        publish_time=row["publish_time"] or "",
        link=row["link"] or "",
        raw_json={},
    )


def _extract_raw_want_count(row) -> int:
    raw_json = row["raw_json"]
    if not raw_json:
        return 0
    try:
        import json

        record = json.loads(raw_json)
    except Exception:
        return 0
    item = record.get("商品信息", {}) or {}
    return _parse_count(
        item.get("“想要”人数")
        or item.get("想要人数")
        or item.get("want_count")
        or item.get("wantCnt")
    )


class TrendSnapshotRefreshService:
    def __init__(
        self,
        db_path: str | None = None,
        *,
        keyword_service: TrendKeywordService | None = None,
        snapshot_service: TrendSnapshotService | None = None,
    ):
        self.db_path = db_path
        self.keyword_service = keyword_service or TrendKeywordService(db_path=db_path)
        self.snapshot_service = snapshot_service or TrendSnapshotService(db_path=db_path)

    async def refresh_enabled_keywords(
        self,
        *,
        limit_per_keyword: int = 40,
    ) -> dict:
        limit_per_keyword = max(1, min(int(limit_per_keyword or 40), 100))
        keywords = await self.keyword_service.list_keywords(include_disabled=False)
        created = []
        skipped = []
        for keyword in keywords:
            snapshot = await asyncio.to_thread(
                self._build_snapshot_payload_sync,
                keyword.id,
                keyword.keyword,
                keyword.category,
                limit_per_keyword,
            )
            if snapshot is None:
                skipped.append({"keyword_id": keyword.id, "keyword": keyword.keyword})
                continue
            created_snapshot = await self.snapshot_service.create_snapshot(snapshot)
            created.append(created_snapshot)
        return {
            "created_count": len(created),
            "skipped_count": len(skipped),
            "items": [item.model_dump(mode="json") for item in created],
            "skipped": skipped,
        }

    def _build_snapshot_payload_sync(
        self,
        keyword_id: int,
        keyword: str,
        category: str,
        limit_per_keyword: int,
    ) -> TrendSnapshotCreate | None:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        with sqlite_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM result_items
                WHERE keyword = ? AND status = 'active'
                ORDER BY crawl_time DESC, id DESC
                LIMIT ?
                """,
                (keyword, limit_per_keyword),
            ).fetchall()
        if not rows:
            return None

        item_samples = []
        seller_count = set()
        new_items_24h = 0
        new_items_3d = 0
        want_total = 0
        for row in rows:
            sample = _row_to_item_sample(row)
            want_count = _extract_raw_want_count(row)
            if want_count:
                sample.want_count = want_count
            want_total += sample.want_count
            if sample.seller_nickname:
                seller_count.add(sample.seller_nickname)
            published_at = _parse_publish_datetime(sample.publish_time)
            if published_at:
                now = datetime.now(timezone.utc)
                delta = now - published_at
                if delta <= timedelta(days=1):
                    new_items_24h += 1
                if delta <= timedelta(days=3):
                    new_items_3d += 1
            item_samples.append(sample)

        prices = [parse_price_value(row["price"]) for row in rows if parse_price_value(row["price"]) is not None]
        return TrendSnapshotCreate(
            keyword_id=keyword_id,
            keyword=keyword,
            category=category,
            total_results=len(rows),
            new_items_24h=new_items_24h,
            new_items_3d=max(new_items_3d, new_items_24h),
            seller_count=len(seller_count),
            min_price=min(prices) if prices else None,
            max_price=max(prices) if prices else None,
            want_count_total=want_total,
            want_count_avg=round(want_total / len(rows), 2) if rows else 0,
            raw_metrics={
                "source": "result_items",
                "limit_per_keyword": limit_per_keyword,
                "sample_count": len(rows),
            },
            items=item_samples,
        )
