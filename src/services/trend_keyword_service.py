"""
趋势关键词池服务。
"""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from src.domain.models.trend_keyword import (
    TrendKeyword,
    TrendKeywordCreate,
    TrendKeywordUpdate,
)
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection


class TrendKeywordConflictError(ValueError):
    """关键词已存在。"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_keyword(row) -> TrendKeyword:
    payload = dict(row)
    payload["enabled"] = bool(payload["enabled"])
    return TrendKeyword(**payload)


class TrendKeywordService:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    async def list_keywords(self, *, include_disabled: bool = False) -> list[TrendKeyword]:
        return await asyncio.to_thread(self._list_keywords_sync, include_disabled)

    async def get_keyword(self, keyword_id: int) -> Optional[TrendKeyword]:
        return await asyncio.to_thread(self._get_keyword_sync, keyword_id)

    async def create_keyword(self, payload: TrendKeywordCreate) -> TrendKeyword:
        return await asyncio.to_thread(self._create_keyword_sync, payload)

    async def update_keyword(
        self,
        keyword_id: int,
        payload: TrendKeywordUpdate,
    ) -> Optional[TrendKeyword]:
        return await asyncio.to_thread(self._update_keyword_sync, keyword_id, payload)

    async def delete_keyword(self, keyword_id: int) -> bool:
        return await asyncio.to_thread(self._delete_keyword_sync, keyword_id)

    def _list_keywords_sync(self, include_disabled: bool) -> list[TrendKeyword]:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        where_clause = "" if include_disabled else "WHERE enabled = 1"
        with sqlite_connection(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM trend_keywords
                {where_clause}
                ORDER BY category ASC, keyword ASC, id ASC
                """
            ).fetchall()
        return [_row_to_keyword(row) for row in rows]

    def _get_keyword_sync(self, keyword_id: int) -> Optional[TrendKeyword]:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        with sqlite_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM trend_keywords WHERE id = ?",
                (keyword_id,),
            ).fetchone()
        return _row_to_keyword(row) if row else None

    def _create_keyword_sync(self, payload: TrendKeywordCreate) -> TrendKeyword:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        timestamp = _now_iso()
        with sqlite_connection(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO trend_keywords (
                        keyword, category, enabled, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload.keyword,
                        payload.category,
                        int(payload.enabled),
                        payload.notes,
                        timestamp,
                        timestamp,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise TrendKeywordConflictError("趋势关键词已存在。") from exc
        created = self._get_keyword_sync(int(cursor.lastrowid))
        if created is None:
            raise RuntimeError("趋势关键词创建后未能读取。")
        return created

    def _update_keyword_sync(
        self,
        keyword_id: int,
        payload: TrendKeywordUpdate,
    ) -> Optional[TrendKeyword]:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        values = payload.model_dump(exclude_unset=True)
        if not values:
            return self._get_keyword_sync(keyword_id)

        assignments = []
        params: list = []
        for field_name in ("keyword", "category", "enabled", "notes"):
            if field_name not in values:
                continue
            assignments.append(f"{field_name} = ?")
            value = values[field_name]
            params.append(int(value) if field_name == "enabled" else value)
        assignments.append("updated_at = ?")
        params.append(_now_iso())
        params.append(keyword_id)

        with sqlite_connection(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    f"""
                    UPDATE trend_keywords
                    SET {", ".join(assignments)}
                    WHERE id = ?
                    """,
                    tuple(params),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise TrendKeywordConflictError("趋势关键词已存在。") from exc
        if cursor.rowcount <= 0:
            return None
        return self._get_keyword_sync(keyword_id)

    def _delete_keyword_sync(self, keyword_id: int) -> bool:
        bootstrap_sqlite_storage(self.db_path, legacy_config_file=None)
        with sqlite_connection(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM trend_keywords WHERE id = ?",
                (keyword_id,),
            )
            conn.commit()
        return cursor.rowcount > 0
