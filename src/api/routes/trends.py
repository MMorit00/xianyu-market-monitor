"""
闲鱼站内趋势雷达路由。
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_trend_keyword_service
from src.domain.models.trend_keyword import TrendKeywordCreate, TrendKeywordUpdate
from src.services.trend_keyword_service import (
    TrendKeywordConflictError,
    TrendKeywordService,
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
