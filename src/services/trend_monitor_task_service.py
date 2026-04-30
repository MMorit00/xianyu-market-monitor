"""
把趋势关键词同步为实际闲鱼监控任务。
"""
from __future__ import annotations

from typing import Any

from src.domain.models.task import Task, TaskCreate, TaskUpdate
from src.domain.models.trend_monitor_task import TrendMonitorTaskSyncRequest
from src.services.task_service import TaskService
from src.services.trend_keyword_service import TrendKeywordService


SILENT_KEYWORD_RULE = "__mozshop_seller_radar_silent_rule__"
TASK_NAME_PREFIX = "卖家雷达"


def _normalize_key(value: str | None) -> str:
    return str(value or "").strip().lower()


def _task_name(keyword: str) -> str:
    return f"{TASK_NAME_PREFIX} - {keyword.strip()}"


def _description(keyword: str, notes: str = "") -> str:
    suffix = f"\n备注：{notes.strip()}" if notes and notes.strip() else ""
    return (
        f"卖家雷达趋势观察任务：抓取闲鱼站内“{keyword}”相关新品，"
        "只负责沉淀市场样本，最终由每日 AI 机会日报统一判断是否值得跟进。"
        f"{suffix}"
    )


class TrendMonitorTaskService:
    def __init__(
        self,
        *,
        keyword_service: TrendKeywordService,
        task_service: TaskService,
    ):
        self.keyword_service = keyword_service
        self.task_service = task_service

    async def sync_monitor_tasks(self, payload: TrendMonitorTaskSyncRequest) -> dict[str, Any]:
        keywords = await self.keyword_service.list_keywords(include_disabled=False)
        tasks = await self.task_service.get_all_tasks()
        by_name = {_normalize_key(task.task_name): task for task in tasks}
        by_keyword: dict[str, list[Task]] = {}
        for task in tasks:
            by_keyword.setdefault(_normalize_key(task.keyword), []).append(task)

        items: list[dict[str, Any]] = []
        created_count = 0
        updated_count = 0
        existing_count = 0
        skipped_count = 0

        for keyword in keywords:
            task_name = _task_name(keyword.keyword)
            existing_radar_task = by_name.get(_normalize_key(task_name))
            if existing_radar_task:
                action = "existing"
                task = existing_radar_task
                if payload.update_existing:
                    updated_task = await self._update_radar_task_if_needed(
                        existing_radar_task,
                        keyword.keyword,
                        keyword.notes,
                        payload,
                    )
                    if updated_task.id == existing_radar_task.id and updated_task != existing_radar_task:
                        task = updated_task
                        action = "updated"
                        updated_count += 1
                    else:
                        existing_count += 1
                else:
                    existing_count += 1
                items.append(self._item(keyword.id, keyword.keyword, task, action))
                continue

            reusable_task = self._find_reusable_task(by_keyword.get(_normalize_key(keyword.keyword), []))
            if reusable_task:
                existing_count += 1
                items.append(
                    self._item(
                        keyword.id,
                        keyword.keyword,
                        reusable_task,
                        "existing_keyword_task",
                        "已有同关键词监控任务，未重复创建。",
                    )
                )
                continue

            task = await self.task_service.create_task(
                self._build_task_create(keyword.keyword, keyword.notes, payload)
            )
            created_count += 1
            items.append(self._item(keyword.id, keyword.keyword, task, "created"))

        return {
            "created_count": created_count,
            "updated_count": updated_count,
            "existing_count": existing_count,
            "skipped_count": skipped_count,
            "items": items,
        }

    def _find_reusable_task(self, tasks: list[Task]) -> Task | None:
        for task in tasks:
            if task.enabled:
                return task
        return None

    def _build_task_create(
        self,
        keyword: str,
        notes: str,
        payload: TrendMonitorTaskSyncRequest,
    ) -> TaskCreate:
        return TaskCreate(
            task_name=_task_name(keyword),
            enabled=payload.enabled,
            keyword=keyword,
            description=_description(keyword, notes),
            analyze_images=False,
            max_pages=payload.max_pages,
            personal_only=payload.personal_only,
            min_price=payload.min_price,
            max_price=payload.max_price,
            cron=payload.cron,
            ai_prompt_base_file="prompts/base_prompt.txt",
            ai_prompt_criteria_file="",
            account_strategy="auto",
            free_shipping=payload.free_shipping,
            new_publish_option=payload.new_publish_option,
            region=payload.region,
            decision_mode="keyword",
            keyword_rules=[SILENT_KEYWORD_RULE],
        )

    async def _update_radar_task_if_needed(
        self,
        task: Task,
        keyword: str,
        notes: str,
        payload: TrendMonitorTaskSyncRequest,
    ) -> Task:
        update_values = {
            "task_name": _task_name(keyword),
            "enabled": payload.enabled,
            "keyword": keyword,
            "description": _description(keyword, notes),
            "analyze_images": False,
            "max_pages": payload.max_pages,
            "personal_only": payload.personal_only,
            "cron": payload.cron,
            "ai_prompt_base_file": "prompts/base_prompt.txt",
            "ai_prompt_criteria_file": "",
            "account_strategy": "auto",
            "free_shipping": payload.free_shipping,
            "new_publish_option": payload.new_publish_option,
            "region": payload.region,
            "decision_mode": "keyword",
            "keyword_rules": [SILENT_KEYWORD_RULE],
        }
        if "min_price" in payload.model_fields_set:
            update_values["min_price"] = payload.min_price
        if "max_price" in payload.model_fields_set:
            update_values["max_price"] = payload.max_price

        current = task.model_dump()
        changed_values = {
            key: value
            for key, value in update_values.items()
            if current.get(key) != value
        }
        if not changed_values:
            return task
        return await self.task_service.update_task(task.id, TaskUpdate(**changed_values))

    def _item(
        self,
        keyword_id: int,
        keyword: str,
        task: Task,
        action: str,
        reason: str = "",
    ) -> dict[str, Any]:
        return {
            "keyword_id": keyword_id,
            "keyword": keyword,
            "task_id": task.id,
            "task_name": task.task_name,
            "action": action,
            "reason": reason,
        }
