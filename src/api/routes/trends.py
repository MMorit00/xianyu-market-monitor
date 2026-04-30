"""
闲鱼站内趋势雷达路由。
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import (
    get_scheduler_service,
    get_task_service,
    get_trend_daily_report_service,
    get_trend_keyword_service,
    get_trend_monitor_task_service,
    get_trend_snapshot_refresh_service,
    get_trend_snapshot_service,
)
from src.domain.models.trend_daily_report import (
    TrendDailyReportRunRequest,
    TrendDailyReportTestNotificationRequest,
)
from src.domain.models.trend_keyword import TrendKeywordCreate, TrendKeywordUpdate
from src.domain.models.trend_monitor_task import TrendMonitorTaskSyncRequest
from src.domain.models.trend_snapshot import (
    TrendSnapshotCreate,
    TrendSnapshotRefreshRequest,
)
from src.infrastructure.config.env_manager import env_manager
from src.infrastructure.config.settings import AISettings
from src.services.scheduler_service import SchedulerService
from src.services.task_service import TaskService
from src.services.trend_daily_report_service import TrendDailyReportService
from src.services.trend_keyword_service import (
    TrendKeywordConflictError,
    TrendKeywordService,
)
from src.services.trend_monitor_task_service import TrendMonitorTaskService
from src.services.notification_config_service import load_notification_settings
from src.services.trend_snapshot_refresh_service import TrendSnapshotRefreshService
from src.services.trend_snapshot_service import (
    TrendSnapshotService,
    TrendSnapshotValidationError,
)


router = APIRouter(prefix="/api/trends", tags=["trends"])


def _env_bool(key: str, default: bool = False) -> bool:
    value = env_manager.get_value(key)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


@router.get("/keywords", response_model=dict)
async def list_trend_keywords(
    include_disabled: bool = Query(False),
    service: TrendKeywordService = Depends(get_trend_keyword_service),
):
    keywords = await service.list_keywords(include_disabled=include_disabled)
    return {"items": [item.model_dump(mode="json") for item in keywords]}


@router.post("/keywords", response_model=dict)
async def create_trend_keyword(
    payload: TrendKeywordCreate,
    service: TrendKeywordService = Depends(get_trend_keyword_service),
):
    try:
        keyword = await service.create_keyword(payload)
    except TrendKeywordConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"message": "趋势关键词已创建", "item": keyword.model_dump(mode="json")}


@router.get("/keywords/{keyword_id}", response_model=dict)
async def get_trend_keyword(
    keyword_id: int,
    service: TrendKeywordService = Depends(get_trend_keyword_service),
):
    keyword = await service.get_keyword(keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="趋势关键词不存在")
    return {"item": keyword.model_dump(mode="json")}


@router.patch("/keywords/{keyword_id}", response_model=dict)
async def update_trend_keyword(
    keyword_id: int,
    payload: TrendKeywordUpdate,
    service: TrendKeywordService = Depends(get_trend_keyword_service),
):
    try:
        keyword = await service.update_keyword(keyword_id, payload)
    except TrendKeywordConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not keyword:
        raise HTTPException(status_code=404, detail="趋势关键词不存在")
    return {"message": "趋势关键词已更新", "item": keyword.model_dump(mode="json")}


@router.delete("/keywords/{keyword_id}", response_model=dict)
async def delete_trend_keyword(
    keyword_id: int,
    service: TrendKeywordService = Depends(get_trend_keyword_service),
):
    deleted = await service.delete_keyword(keyword_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="趋势关键词不存在")
    return {"message": "趋势关键词已删除"}


@router.post("/snapshots", response_model=dict)
async def create_trend_snapshot(
    payload: TrendSnapshotCreate,
    service: TrendSnapshotService = Depends(get_trend_snapshot_service),
):
    try:
        snapshot = await service.create_snapshot(payload)
    except TrendSnapshotValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "趋势快照已创建", "item": snapshot.model_dump(mode="json")}


@router.get("/snapshots", response_model=dict)
async def list_trend_snapshots(
    keyword_id: int | None = Query(None),
    keyword: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    service: TrendSnapshotService = Depends(get_trend_snapshot_service),
):
    snapshots = await service.list_snapshots(
        keyword_id=keyword_id,
        keyword=keyword,
        limit=limit,
    )
    return {"items": [item.model_dump(mode="json") for item in snapshots]}


@router.get("/snapshots/{snapshot_id}", response_model=dict)
async def get_trend_snapshot(
    snapshot_id: int,
    include_items: bool = Query(False),
    service: TrendSnapshotService = Depends(get_trend_snapshot_service),
):
    snapshot = await service.get_snapshot(snapshot_id, include_items=include_items)
    if not snapshot:
        raise HTTPException(status_code=404, detail="趋势快照不存在")
    return {"item": snapshot.model_dump(mode="json")}


@router.get("/opportunities", response_model=dict)
async def list_trend_opportunities(
    level: str | None = Query(None, pattern="^[ABCDabcd]$"),
    limit: int = Query(20, ge=1, le=100),
    latest_only: bool = Query(True),
    service: TrendSnapshotService = Depends(get_trend_snapshot_service),
):
    opportunities = await service.list_opportunities(
        level=level,
        limit=limit,
        latest_only=latest_only,
    )
    return {"items": [item.model_dump(mode="json") for item in opportunities]}


@router.post("/snapshots/refresh", response_model=dict)
async def refresh_trend_snapshots(
    payload: TrendSnapshotRefreshRequest | None = None,
    service: TrendSnapshotRefreshService = Depends(get_trend_snapshot_refresh_service),
):
    request_payload = payload or TrendSnapshotRefreshRequest()
    result = await service.refresh_enabled_keywords(
        limit_per_keyword=request_payload.limit_per_keyword,
    )
    return {"message": "趋势快照已刷新", **result}


@router.post("/monitor-tasks/sync", response_model=dict)
async def sync_trend_monitor_tasks(
    payload: TrendMonitorTaskSyncRequest | None = None,
    service: TrendMonitorTaskService = Depends(get_trend_monitor_task_service),
    task_service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    request_payload = payload or TrendMonitorTaskSyncRequest()
    result = await service.sync_monitor_tasks(request_payload)
    tasks = await task_service.get_all_tasks()
    await scheduler_service.reload_jobs(tasks)
    return {"message": "趋势关键词监控任务已同步", **result}


@router.post("/daily-report/run", response_model=dict)
async def run_daily_report(
    payload: TrendDailyReportRunRequest | None = None,
    service: TrendDailyReportService = Depends(get_trend_daily_report_service),
):
    request_payload = payload or TrendDailyReportRunRequest()
    report = await service.run_report(
        candidate_limit=request_payload.candidate_limit,
        push=request_payload.push,
        refresh_snapshots=request_payload.refresh_snapshots,
    )
    return {"message": "闲鱼机会日报已生成", "item": report.model_dump(mode="json")}


@router.get("/daily-report/config", response_model=dict)
async def get_daily_report_config():
    notification_settings = load_notification_settings()
    ai_settings = AISettings()
    return {
        "enabled": _env_bool("TREND_DAILY_REPORT_ENABLED", True),
        "cron": env_manager.get_value("TREND_DAILY_REPORT_CRON", "0 9 * * *"),
        "bark_configured": bool(notification_settings.bark_url),
        "ai_configured": ai_settings.is_configured(),
    }


@router.get("/daily-report/latest", response_model=dict)
async def get_latest_daily_report(
    service: TrendDailyReportService = Depends(get_trend_daily_report_service),
):
    report = await service.get_latest_report()
    if not report:
        raise HTTPException(status_code=404, detail="暂无闲鱼机会日报")
    return {"item": report.model_dump(mode="json")}


@router.post("/daily-report/send-test", response_model=dict)
async def send_daily_report_test_notification(
    payload: TrendDailyReportTestNotificationRequest | None = None,
    service: TrendDailyReportService = Depends(get_trend_daily_report_service),
):
    request_payload = payload or TrendDailyReportTestNotificationRequest()
    result = await service.send_test_notification(
        title=request_payload.title,
        body=request_payload.body,
    )
    return {"message": "测试通知已执行", "result": result}
