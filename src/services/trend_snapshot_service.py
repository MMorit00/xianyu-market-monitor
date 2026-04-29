"""
趋势快照与弱竞争机会评分服务。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from statistics import median
from typing import Optional

from src.domain.models.trend_snapshot import (
    TrendItemSample,
    TrendOpportunity,
    TrendSnapshot,
    TrendSnapshotCreate,
    TrendSnapshotDetail,
    TrendSnapshotItem,
)
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection


EXECUTION_KEYWORDS = (
    "ai",
    "gpt",
    "comfyui",
    "midjourney",
    "提示词",
    "工作流",
    "课程",
    "教程",
    "资料",
    "资料包",
    "模板",
    "素材",
    "副业",
    "软件",
    "插件",
)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9+._-]*|[\u4e00-\u9fff]{2,}")


class TrendSnapshotValidationError(ValueError):
    """趋势快照输入不完整或引用不存在。"""


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return round(max(low, min(high, value)), 2)


def _safe_json_loads(text: str | None, fallback):
    if not text:
        return fallback
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback


def _row_to_snapshot(row) -> TrendSnapshot:
    payload = dict(row)
    payload["title_terms"] = _safe_json_loads(payload.pop("title_terms_json", "[]"), [])
    payload["reasons"] = _safe_json_loads(payload.pop("reasons_json", "[]"), [])
    payload["raw_metrics"] = _safe_json_loads(payload.pop("raw_metrics_json", "{}"), {})
    return TrendSnapshot(**payload)


def _row_to_item(row) -> TrendSnapshotItem:
    payload = dict(row)
    payload["raw_json"] = _safe_json_loads(payload.get("raw_json"), {})
    payload.pop("link_unique_key", None)
    return TrendSnapshotItem(**payload)


def _snapshot_to_opportunity(snapshot: TrendSnapshot) -> TrendOpportunity:
    return TrendOpportunity(
        snapshot_id=snapshot.id,
        keyword_id=snapshot.keyword_id,
        keyword=snapshot.keyword,
        category=snapshot.category,
        snapshot_time=snapshot.snapshot_time,
        opportunity_score=snapshot.opportunity_score,
        opportunity_level=snapshot.opportunity_level,
        growth_score=snapshot.growth_score,
        competition_score=snapshot.competition_score,
        profit_score=snapshot.profit_score,
        freshness_score=snapshot.freshness_score,
        execution_score=snapshot.execution_score,
        reasons=snapshot.reasons,
        action=snapshot.action,
    )


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", "", title or "").lower()


def _extract_title_terms(items: list[TrendItemSample]) -> list[str]:
    counter: Counter[str] = Counter()
    for item in items:
        for token in TOKEN_PATTERN.findall(item.title):
            normalized = token.strip().lower()
            if len(normalized) < 2:
                continue
            counter[normalized] += 1
    return [term for term, _count in counter.most_common(12)]


def _publish_time_bucket(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if any(marker in text for marker in ("刚刚", "分钟前", "小时前", "今天")):
        return "24h"
    if "昨天" in text or "前天" in text:
        return "3d"
    day_match = re.search(r"([0-9]+)\s*天前", text)
    if day_match and int(day_match.group(1)) <= 3:
        return "3d"
    return ""


def _build_item_unique_key(item: TrendItemSample, index: int) -> str:
    if item.link:
        return item.link.split("&", 1)[0]
    if item.item_id:
        return f"item:{item.item_id}"
    seed = json.dumps(
        {
            "index": index,
            "title": item.title,
            "seller": item.seller_nickname,
            "price": item.price,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return "hash:" + hashlib.sha1(seed.encode("utf-8")).hexdigest()


def _compute_metrics(
    payload: TrendSnapshotCreate,
    *,
    keyword: str,
) -> dict:
    items = payload.items
    prices = [item.price for item in items if item.price is not None]
    titles = [_normalize_title(item.title) for item in items if item.title.strip()]
    sellers = {item.seller_nickname for item in items if item.seller_nickname}
    image_keys = [item.image_key for item in items if item.image_key]
    image_counter = Counter(image_keys)
    publish_buckets = [_publish_time_bucket(item.publish_time) for item in items]

    computed_median = float(median(prices)) if prices else None
    total_results = payload.total_results if payload.total_results is not None else len(items)
    new_items_24h = (
        payload.new_items_24h
        if payload.new_items_24h is not None
        else sum(1 for bucket in publish_buckets if bucket == "24h")
    )
    new_items_3d = (
        payload.new_items_3d
        if payload.new_items_3d is not None
        else sum(1 for bucket in publish_buckets if bucket in {"24h", "3d"})
    )
    new_items_3d = max(new_items_3d, new_items_24h)
    want_count_total = (
        payload.want_count_total
        if payload.want_count_total is not None
        else sum(item.want_count for item in items)
    )
    want_count_avg = (
        payload.want_count_avg
        if payload.want_count_avg is not None
        else round(want_count_total / len(items), 2)
        if items
        else 0
    )
    title_repetition_rate = payload.title_repetition_rate
    if title_repetition_rate is None:
        title_repetition_rate = 0
        if titles:
            title_repetition_rate = round((len(titles) - len(set(titles))) / len(titles), 4)

    same_image_count = payload.same_image_count
    if same_image_count is None:
        same_image_count = sum(count - 1 for count in image_counter.values() if count > 1)

    median_price = payload.median_price if payload.median_price is not None else computed_median
    low_price_item_ratio = payload.low_price_item_ratio
    if low_price_item_ratio is None:
        low_price_item_ratio = 0
        if prices and median_price and median_price > 0:
            low_price_item_ratio = round(
                sum(1 for price in prices if price <= median_price * 0.7) / len(prices),
                4,
            )

    return {
        "keyword": keyword,
        "total_results": max(int(total_results or 0), 0),
        "new_items_24h": max(int(new_items_24h or 0), 0),
        "new_items_3d": max(int(new_items_3d or 0), 0),
        "seller_count": (
            payload.seller_count if payload.seller_count is not None else len(sellers)
        ),
        "new_seller_count": payload.new_seller_count or 0,
        "min_price": payload.min_price if payload.min_price is not None else (min(prices) if prices else None),
        "max_price": payload.max_price if payload.max_price is not None else (max(prices) if prices else None),
        "median_price": median_price,
        "want_count_total": max(int(want_count_total or 0), 0),
        "want_count_avg": round(float(want_count_avg or 0), 2),
        "title_terms": (
            payload.title_terms if payload.title_terms is not None else _extract_title_terms(items)
        ),
        "title_repetition_rate": _clamp(float(title_repetition_rate or 0), 0, 1),
        "same_image_count": max(int(same_image_count or 0), 0),
        "low_price_item_ratio": _clamp(float(low_price_item_ratio or 0), 0, 1),
        "execution_score": payload.execution_score,
        "raw_metrics": payload.raw_metrics,
    }


def _score_execution(keyword: str, explicit_score: Optional[float]) -> float:
    if explicit_score is not None:
        return _clamp(explicit_score)
    text = keyword.lower()
    if any(term in text for term in EXECUTION_KEYWORDS):
        return 85
    return 62


def _score_profit(median_price: Optional[float], low_price_item_ratio: float) -> float:
    if median_price is None:
        score = 50
    elif median_price < 10:
        score = 35
    elif median_price <= 300:
        score = 85
    elif median_price <= 1000:
        score = 70
    else:
        score = 55
    return _clamp(score - low_price_item_ratio * 25)


def _build_score(metrics: dict) -> dict:
    new_items_24h = metrics["new_items_24h"]
    new_items_3d = metrics["new_items_3d"]
    total_results = metrics["total_results"]
    seller_count = metrics["seller_count"]
    title_repetition_rate = metrics["title_repetition_rate"]
    same_image_count = metrics["same_image_count"]
    low_price_item_ratio = metrics["low_price_item_ratio"]
    want_count_avg = metrics["want_count_avg"]

    growth_score = _clamp(
        new_items_24h * 10
        + max(new_items_3d - new_items_24h, 0) * 4
        + min(total_results, 50) * 0.2
        + min(want_count_avg, 40) * 1.5
    )
    competition_score = _clamp(
        100
        - max(seller_count - 5, 0) * 3
        - title_repetition_rate * 45
        - low_price_item_ratio * 35
        - same_image_count * 4
    )
    profit_score = _score_profit(metrics["median_price"], low_price_item_ratio)
    if new_items_3d <= 0:
        freshness_score = 45
    else:
        freshness_score = 45 + min(new_items_24h / new_items_3d, 1) * 45
    if total_results <= 30 and new_items_24h > 0:
        freshness_score += 10
    freshness_score = _clamp(freshness_score)
    execution_score = _score_execution(metrics["keyword"], metrics["execution_score"])

    opportunity_score = _clamp(
        growth_score * 0.30
        + competition_score * 0.25
        + profit_score * 0.15
        + freshness_score * 0.15
        + execution_score * 0.15
    )
    if opportunity_score >= 75:
        level = "A"
        action = "今天生成上架测试稿，建议用 2-3 个标题/主图角度小流量测试。"
    elif opportunity_score >= 60:
        level = "B"
        action = "继续观察 1-3 天；如果新增商品和互动继续上升，再生成测试稿。"
    elif opportunity_score >= 45:
        level = "C"
        action = "有热度但暂不建议立即跟进，先看竞争是否继续加重。"
    else:
        level = "D"
        action = "暂时放弃，不进入商品候选池。"

    reasons = []
    if growth_score >= 70:
        reasons.append("增长较快，近 24 小时或近 3 天上新明显。")
    elif growth_score >= 50:
        reasons.append("有一定增长，需要继续观察能否延续。")
    else:
        reasons.append("增长信号偏弱，暂时不能证明需求在放大。")

    if competition_score >= 75:
        reasons.append("竞争压力暂时不高，卖家数量、标题重复或同款图压力可控。")
    elif competition_score < 45:
        reasons.append("竞争压力偏高，可能已经出现同质化或低价挤压。")

    if profit_score >= 70:
        reasons.append("价格带相对健康，具备测试利润空间。")
    elif profit_score < 45:
        reasons.append("价格带偏低或低价占比高，需要谨慎。")

    if freshness_score >= 70:
        reasons.append("新鲜度较高，更接近刚启动的站内趋势。")

    if execution_score >= 80:
        reasons.append("与 MOZShop 的课程、资料、工具或工作流商品形态匹配度高。")

    return {
        "growth_score": growth_score,
        "competition_score": competition_score,
        "profit_score": profit_score,
        "freshness_score": freshness_score,
        "execution_score": execution_score,
        "opportunity_score": opportunity_score,
        "opportunity_level": level,
        "reasons": reasons,
        "action": action,
    }


class TrendSnapshotService:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    async def create_snapshot(self, payload: TrendSnapshotCreate) -> TrendSnapshotDetail:
        return await asyncio.to_thread(self._create_snapshot_sync, payload)

    async def get_snapshot(
        self,
        snapshot_id: int,
        *,
        include_items: bool = False,
    ) -> Optional[TrendSnapshot | TrendSnapshotDetail]:
        return await asyncio.to_thread(
            self._get_snapshot_sync,
            snapshot_id,
            include_items,
        )

    async def list_snapshots(
        self,
        *,
        keyword_id: int | None = None,
        keyword: str | None = None,
        limit: int = 50,
    ) -> list[TrendSnapshot]:
        return await asyncio.to_thread(
            self._list_snapshots_sync,
            keyword_id,
            keyword,
            limit,
        )

    async def list_opportunities(
        self,
        *,
        level: str | None = None,
        limit: int = 20,
        latest_only: bool = True,
    ) -> list[TrendOpportunity]:
        return await asyncio.to_thread(
            self._list_opportunities_sync,
            level,
            limit,
            latest_only,
        )

    def _create_snapshot_sync(self, payload: TrendSnapshotCreate) -> TrendSnapshotDetail:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        snapshot_time = payload.snapshot_time or _now_utc()
        created_at = _now_utc()
        with sqlite_connection(self.db_path) as conn:
            keyword_id, keyword, category = self._resolve_keyword(conn, payload)
            metrics = _compute_metrics(payload, keyword=keyword)
            score = _build_score(metrics)
            cursor = conn.execute(
                """
                INSERT INTO trend_snapshots (
                    keyword_id, keyword, category, snapshot_time, total_results,
                    new_items_24h, new_items_3d, seller_count, new_seller_count,
                    min_price, max_price, median_price, want_count_total,
                    want_count_avg, title_terms_json, title_repetition_rate,
                    same_image_count, low_price_item_ratio, opportunity_score,
                    opportunity_level, growth_score, competition_score, profit_score,
                    freshness_score, execution_score, reasons_json, action,
                    raw_metrics_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    keyword_id,
                    keyword,
                    category,
                    _to_iso(snapshot_time),
                    metrics["total_results"],
                    metrics["new_items_24h"],
                    metrics["new_items_3d"],
                    metrics["seller_count"],
                    metrics["new_seller_count"],
                    metrics["min_price"],
                    metrics["max_price"],
                    metrics["median_price"],
                    metrics["want_count_total"],
                    metrics["want_count_avg"],
                    json.dumps(metrics["title_terms"], ensure_ascii=False),
                    metrics["title_repetition_rate"],
                    metrics["same_image_count"],
                    metrics["low_price_item_ratio"],
                    score["opportunity_score"],
                    score["opportunity_level"],
                    score["growth_score"],
                    score["competition_score"],
                    score["profit_score"],
                    score["freshness_score"],
                    score["execution_score"],
                    json.dumps(score["reasons"], ensure_ascii=False),
                    score["action"],
                    json.dumps(metrics["raw_metrics"], ensure_ascii=False),
                    _to_iso(created_at),
                ),
            )
            snapshot_id = int(cursor.lastrowid)
            self._insert_items(conn, snapshot_id, payload.items)
            conn.commit()

        snapshot = self._get_snapshot_sync(snapshot_id, include_items=True)
        if snapshot is None:
            raise RuntimeError("趋势快照创建后未能读取。")
        return snapshot

    def _resolve_keyword(self, conn, payload: TrendSnapshotCreate) -> tuple[int | None, str, str]:
        keyword_id = payload.keyword_id
        keyword = payload.keyword
        category = payload.category
        if keyword_id is not None:
            row = conn.execute(
                "SELECT id, keyword, category FROM trend_keywords WHERE id = ?",
                (keyword_id,),
            ).fetchone()
            if row is None:
                raise TrendSnapshotValidationError("趋势关键词不存在。")
            keyword = str(row["keyword"])
            category = category or str(row["category"] or "")
        if not keyword:
            raise TrendSnapshotValidationError("必须提供 keyword_id 或 keyword。")
        return keyword_id, keyword, category

    def _insert_items(
        self,
        conn,
        snapshot_id: int,
        items: list[TrendItemSample],
    ) -> None:
        for index, item in enumerate(items):
            conn.execute(
                """
                INSERT OR IGNORE INTO trend_items (
                    snapshot_id, item_id, title, price, price_display,
                    seller_nickname, want_count, publish_time, link, image_key,
                    raw_json, link_unique_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    item.item_id,
                    item.title,
                    item.price,
                    item.price_display,
                    item.seller_nickname,
                    item.want_count,
                    item.publish_time,
                    item.link,
                    item.image_key,
                    json.dumps(item.raw_json, ensure_ascii=False),
                    _build_item_unique_key(item, index),
                ),
            )

    def _get_snapshot_sync(
        self,
        snapshot_id: int,
        include_items: bool,
    ) -> Optional[TrendSnapshot | TrendSnapshotDetail]:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        with sqlite_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM trend_snapshots WHERE id = ?",
                (snapshot_id,),
            ).fetchone()
            if row is None:
                return None
            snapshot = _row_to_snapshot(row)
            if not include_items:
                return snapshot
            item_rows = conn.execute(
                """
                SELECT *
                FROM trend_items
                WHERE snapshot_id = ?
                ORDER BY id ASC
                """,
                (snapshot_id,),
            ).fetchall()
        return TrendSnapshotDetail(
            **snapshot.model_dump(mode="python"),
            items=[_row_to_item(item_row) for item_row in item_rows],
        )

    def _list_snapshots_sync(
        self,
        keyword_id: int | None,
        keyword: str | None,
        limit: int,
    ) -> list[TrendSnapshot]:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        limit = max(1, min(int(limit or 50), 200))
        clauses = []
        params: list = []
        if keyword_id is not None:
            clauses.append("keyword_id = ?")
            params.append(keyword_id)
        if keyword:
            clauses.append("keyword = ?")
            params.append(keyword.strip())
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with sqlite_connection(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM trend_snapshots
                {where_clause}
                ORDER BY snapshot_time DESC, id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [_row_to_snapshot(row) for row in rows]

    def _list_opportunities_sync(
        self,
        level: str | None,
        limit: int,
        latest_only: bool,
    ) -> list[TrendOpportunity]:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        limit = max(1, min(int(limit or 20), 100))
        level = level.upper().strip() if level else None
        with sqlite_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM trend_snapshots
                ORDER BY snapshot_time DESC, id DESC
                """
            ).fetchall()
        snapshots = [_row_to_snapshot(row) for row in rows]
        if latest_only:
            latest = {}
            for snapshot in snapshots:
                key = snapshot.keyword_id if snapshot.keyword_id is not None else snapshot.keyword
                if key not in latest:
                    latest[key] = snapshot
            snapshots = list(latest.values())
        if level:
            snapshots = [item for item in snapshots if item.opportunity_level == level]
        snapshots.sort(
            key=lambda item: (
                item.opportunity_score,
                item.snapshot_time,
                item.id,
            ),
            reverse=True,
        )
        return [_snapshot_to_opportunity(snapshot) for snapshot in snapshots[:limit]]
