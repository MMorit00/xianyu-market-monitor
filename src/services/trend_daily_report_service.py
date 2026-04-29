"""
每日 AI 闲鱼机会日报服务。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import requests

from src.domain.models.trend_daily_report import TrendDailyReport
from src.domain.models.trend_snapshot import TrendOpportunity
from src.infrastructure.config.settings import NotificationSettings
from src.infrastructure.external.ai_client import AIClient
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection
from src.services.ai_response_parser import parse_ai_response_json
from src.services.notification_config_service import load_notification_settings
from src.services.trend_snapshot_service import TrendSnapshotService


REPORT_TIMEZONE = ZoneInfo("Asia/Shanghai")
DEFAULT_REPORT_TITLE = "闲鱼 AI 机会日报"
MOZSHOP_SELLER_SYSTEM_PROMPT = """
你是 MOZShop 的闲鱼卖家运营助理。你的任务不是判断买不买，而是判断一个站内趋势是否适合我们卖。
优先考虑数字资料、课程、模板、工作流、提示词、教程、工具包。
排除实体重库存、高售后、侵权、灰产、医疗金融等风险方向。
请只基于输入数据做判断，不要编造销量、平台规则或确定性收益。
输出必须是 JSON，不要包含 Markdown。
""".strip()


class DailyReportAIReviewer(Protocol):
    async def review(self, opportunities: list[TrendOpportunity]) -> dict[str, Any]:
        ...


class DailyReportNotifier(Protocol):
    async def send(self, title: str, body: str) -> dict[str, str | bool]:
        ...


class TrendDailyReportAIReviewer:
    def __init__(self, ai_client: AIClient | None = None):
        self.ai_client = ai_client or AIClient()

    async def review(self, opportunities: list[TrendOpportunity]) -> dict[str, Any]:
        if not opportunities:
            return _build_empty_review()
        if not self.ai_client.is_available():
            return _build_rule_based_review(opportunities, note="AI 未配置，使用规则评分生成日报。")

        payload = _build_ai_input_payload(opportunities)
        messages = [
            {"role": "system", "content": MOZSHOP_SELLER_SYSTEM_PROMPT},
            {"role": "user", "content": _build_ai_user_prompt(payload)},
        ]
        response_text = await self.ai_client._call_ai(  # noqa: SLF001 - internal compatibility wrapper
            messages,
            temperature=0.2,
            max_output_tokens=3000,
            enable_json_output=True,
        )
        review = parse_ai_response_json(response_text)
        return _normalize_ai_review(review, opportunities)


class BarkDailyReportNotifier:
    def __init__(self, settings: NotificationSettings | None = None):
        self.settings = settings

    async def send(self, title: str, body: str) -> dict[str, str | bool]:
        settings = self.settings or load_notification_settings()
        if not settings.bark_url:
            return {
                "channel": "bark",
                "success": False,
                "message": "BARK_URL 未配置",
            }
        payload = {
            "title": title,
            "body": body,
            "level": "timeSensitive",
            "group": "闲鱼机会日报",
        }
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    settings.bark_url,
                    json=payload,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    timeout=10,
                ),
            )
            response.raise_for_status()
            return {"channel": "bark", "success": True, "message": "发送成功"}
        except Exception as exc:
            return {"channel": "bark", "success": False, "message": str(exc)}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _report_date() -> str:
    return datetime.now(REPORT_TIMEZONE).strftime("%Y-%m-%d")


def _safe_json_loads(text: str | None, fallback):
    if not text:
        return fallback
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback


def _row_to_report(row) -> TrendDailyReport:
    payload = dict(row)
    payload["candidate_snapshot_ids"] = _safe_json_loads(
        payload.pop("candidate_snapshot_ids_json", "[]"),
        [],
    )
    payload["ai_review"] = _safe_json_loads(payload.pop("ai_review_json", "{}"), {})
    return TrendDailyReport(**payload)


def _build_ai_input_payload(opportunities: list[TrendOpportunity]) -> dict[str, Any]:
    return {
        "business_context": {
            "seller": "MOZShop",
            "preferred_products": ["数字资料", "课程", "模板", "工作流", "提示词", "教程", "工具包"],
            "avoid_products": ["实体重库存", "高售后", "侵权", "灰产", "医疗金融"],
        },
        "candidates": [
            {
                "snapshot_id": item.snapshot_id,
                "keyword": item.keyword,
                "category": item.category,
                "opportunity_score": item.opportunity_score,
                "opportunity_level": item.opportunity_level,
                "growth_score": item.growth_score,
                "competition_score": item.competition_score,
                "profit_score": item.profit_score,
                "freshness_score": item.freshness_score,
                "execution_score": item.execution_score,
                "rule_reasons": item.reasons,
                "rule_action": item.action,
            }
            for item in opportunities
        ],
    }


def _build_ai_user_prompt(payload: dict[str, Any]) -> str:
    return (
        "请审核以下闲鱼趋势候选，选出最多 5 个适合今天推送给卖家的机会。\n"
        "返回 JSON 格式：\n"
        "{\n"
        '  "daily_summary": "一句话总结今天值得关注的方向",\n'
        '  "items": [\n'
        "    {\n"
        '      "snapshot_id": 1,\n'
        '      "keyword": "关键词",\n'
        '      "rank": "A/B/C/D",\n'
        '      "should_push": true,\n'
        '      "why": "为什么值得看",\n'
        '      "sell_angle": "适合我们怎么卖",\n'
        '      "advantages": ["优势1", "优势2"],\n'
        '      "risks": ["风险1", "风险2"],\n'
        '      "next_action": "下一步建议"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "候选数据：\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _build_empty_review() -> dict[str, Any]:
    return {
        "daily_summary": "今日暂无明显闲鱼机会。",
        "items": [],
    }


def _build_rule_based_review(
    opportunities: list[TrendOpportunity],
    *,
    note: str = "",
) -> dict[str, Any]:
    items = []
    for opportunity in opportunities[:5]:
        items.append(
            {
                "snapshot_id": opportunity.snapshot_id,
                "keyword": opportunity.keyword,
                "rank": opportunity.opportunity_level,
                "should_push": True,
                "why": "；".join(opportunity.reasons[:2]) or "规则评分较高，建议查看。",
                "sell_angle": "优先判断是否能做成资料包、教程、模板或工作流。",
                "advantages": ["已有规则评分支撑", "可由人工快速判断是否适合 MOZShop"],
                "risks": ["AI 审核未执行，需人工复核", "需要确认交付能力和平台风险"],
                "next_action": opportunity.action or "进入人工查看。",
            }
        )
    return {
        "daily_summary": note or "以下为规则评分筛出的闲鱼机会。",
        "items": items,
    }


def _normalize_ai_review(
    review: dict[str, Any],
    opportunities: list[TrendOpportunity],
) -> dict[str, Any]:
    if not isinstance(review, dict):
        return _build_rule_based_review(opportunities, note="AI 返回格式异常，已回退到规则评分。")
    summary = str(review.get("daily_summary") or "").strip()
    if not summary:
        summary = "今天建议优先查看以下闲鱼机会。"
    source_by_id = {item.snapshot_id: item for item in opportunities}
    source_by_keyword = {item.keyword: item for item in opportunities}
    normalized_items = []
    raw_items = review.get("items") if isinstance(review.get("items"), list) else []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        source = None
        snapshot_id = raw_item.get("snapshot_id")
        try:
            snapshot_id = int(snapshot_id)
        except (TypeError, ValueError):
            snapshot_id = None
        if snapshot_id is not None:
            source = source_by_id.get(snapshot_id)
        keyword = str(raw_item.get("keyword") or "").strip()
        if source is None and keyword:
            source = source_by_keyword.get(keyword)
        if source is None:
            continue
        normalized_items.append(
            {
                "snapshot_id": source.snapshot_id,
                "keyword": source.keyword,
                "rank": str(raw_item.get("rank") or source.opportunity_level).strip()[:1].upper()
                or source.opportunity_level,
                "should_push": bool(raw_item.get("should_push", True)),
                "why": str(raw_item.get("why") or "AI 建议查看。").strip(),
                "sell_angle": str(raw_item.get("sell_angle") or "待人工判断卖法。").strip(),
                "advantages": _normalize_text_list(raw_item.get("advantages")),
                "risks": _normalize_text_list(raw_item.get("risks")),
                "next_action": str(raw_item.get("next_action") or source.action).strip(),
            }
        )
        if len(normalized_items) >= 5:
            break
    if not normalized_items:
        return _build_rule_based_review(opportunities, note=summary)
    return {"daily_summary": summary, "items": normalized_items}


def _normalize_text_list(value) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    output = []
    for item in value:
        text = str(item or "").strip()
        if text:
            output.append(text)
    return output[:4]


def _format_push_body(review: dict[str, Any]) -> str:
    lines = ["【闲鱼 AI 机会日报】"]
    summary = str(review.get("daily_summary") or "").strip()
    if summary:
        lines.append(summary)
    items = review.get("items") if isinstance(review.get("items"), list) else []
    push_items = [item for item in items if item.get("should_push", True)]
    if not push_items:
        lines.append("")
        lines.append("今日暂无明显机会。")
        return "\n".join(lines)
    for index, item in enumerate(push_items[:5], start=1):
        lines.append("")
        lines.append(f"{index}. {item.get('keyword', '未知关键词')} {item.get('rank', '')}".strip())
        why = str(item.get("why") or "").strip()
        if why:
            lines.append(f"原因：{why}")
        angle = str(item.get("sell_angle") or "").strip()
        if angle:
            lines.append(f"卖法：{angle}")
        risks = _normalize_text_list(item.get("risks"))
        if risks:
            lines.append(f"风险：{'；'.join(risks[:2])}")
        action = str(item.get("next_action") or "").strip()
        if action:
            lines.append(f"建议：{action}")
    return "\n".join(lines)


class TrendDailyReportService:
    def __init__(
        self,
        db_path: str | None = None,
        *,
        snapshot_service: TrendSnapshotService | None = None,
        ai_reviewer: DailyReportAIReviewer | None = None,
        notifier: DailyReportNotifier | None = None,
    ):
        self.db_path = db_path
        self.snapshot_service = snapshot_service or TrendSnapshotService(db_path=db_path)
        self.ai_reviewer = ai_reviewer or TrendDailyReportAIReviewer()
        self.notifier = notifier or BarkDailyReportNotifier()

    async def run_report(
        self,
        *,
        candidate_limit: int = 10,
        push: bool = True,
    ) -> TrendDailyReport:
        candidate_limit = max(1, min(int(candidate_limit or 10), 20))
        created_at = _now_iso()
        opportunities = await self.snapshot_service.list_opportunities(
            limit=candidate_limit,
            latest_only=True,
        )
        candidate_ids = [item.snapshot_id for item in opportunities]
        try:
            ai_review = await self.ai_reviewer.review(opportunities)
            status = "completed"
            error_message = ""
        except Exception as exc:
            ai_review = _build_rule_based_review(
                opportunities,
                note="AI 审核失败，已回退到规则评分。",
            )
            status = "completed_with_ai_error"
            error_message = str(exc)

        push_title = DEFAULT_REPORT_TITLE
        push_body = _format_push_body(ai_review)
        push_status = "skipped"
        sent_at = None
        if push:
            push_result = await self.notifier.send(push_title, push_body)
            push_status = "sent" if push_result.get("success") else "failed"
            if push_status == "sent":
                sent_at = _now_iso()
            elif push_result.get("message"):
                error_message = (
                    f"{error_message}; {push_result['message']}"
                    if error_message
                    else str(push_result["message"])
                )

        report_id = await asyncio.to_thread(
            self._insert_report_sync,
            {
                "report_date": _report_date(),
                "status": status,
                "candidate_snapshot_ids": candidate_ids,
                "ai_review": ai_review,
                "push_title": push_title,
                "push_body": push_body,
                "push_channel": "bark",
                "push_status": push_status,
                "error_message": error_message,
                "created_at": created_at,
                "sent_at": sent_at,
            },
        )
        report = await self.get_report(report_id)
        if report is None:
            raise RuntimeError("日报创建后未能读取。")
        return report

    async def get_latest_report(self) -> TrendDailyReport | None:
        return await asyncio.to_thread(self._get_latest_report_sync)

    async def get_report(self, report_id: int) -> TrendDailyReport | None:
        return await asyncio.to_thread(self._get_report_sync, report_id)

    async def send_test_notification(
        self,
        *,
        title: str = "闲鱼 AI 机会日报测试",
        body: str = "这是一条 Bark 日报测试通知。",
    ) -> dict[str, str | bool]:
        return await self.notifier.send(title, body)

    def _insert_report_sync(self, payload: dict[str, Any]) -> int:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        with sqlite_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO trend_daily_reports (
                    report_date, status, candidate_snapshot_ids_json, ai_review_json,
                    push_title, push_body, push_channel, push_status, error_message,
                    created_at, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["report_date"],
                    payload["status"],
                    json.dumps(payload["candidate_snapshot_ids"], ensure_ascii=False),
                    json.dumps(payload["ai_review"], ensure_ascii=False),
                    payload["push_title"],
                    payload["push_body"],
                    payload["push_channel"],
                    payload["push_status"],
                    payload["error_message"],
                    payload["created_at"],
                    payload["sent_at"],
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def _get_report_sync(self, report_id: int) -> TrendDailyReport | None:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        with sqlite_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM trend_daily_reports WHERE id = ?",
                (report_id,),
            ).fetchone()
        return _row_to_report(row) if row else None

    def _get_latest_report_sync(self) -> TrendDailyReport | None:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        with sqlite_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM trend_daily_reports
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        return _row_to_report(row) if row else None
