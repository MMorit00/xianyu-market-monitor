"""
闲鱼站内趋势雷达路由。
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_trend_keyword_service, get_trend_snapshot_service
from src.domain.models.trend_keyword import TrendKeywordCreate, TrendKeywordUpdate
from src.domain.models.trend_snapshot import TrendSnapshotCreate
from src.services.trend_keyword_service import (
    TrendKeywordConflictError,
    TrendKeywordService,
)
from src.services.trend_snapshot_service import (
    TrendSnapshotService,
    TrendSnapshotValidationError,
)


router = APIRouter(prefix="/api/trends", tags=["trends"])


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
