"""
SQLite 连接与 schema 初始化。
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.infrastructure.persistence.storage_names import DEFAULT_DATABASE_PATH


BUSY_TIMEOUT_MS = 5000

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS app_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        task_name TEXT NOT NULL,
        enabled INTEGER NOT NULL,
        keyword TEXT NOT NULL,
        description TEXT,
        analyze_images INTEGER NOT NULL,
        max_pages INTEGER NOT NULL,
        personal_only INTEGER NOT NULL,
        min_price TEXT,
        max_price TEXT,
        cron TEXT,
        ai_prompt_base_file TEXT NOT NULL,
        ai_prompt_criteria_file TEXT NOT NULL,
        account_state_file TEXT,
        account_strategy TEXT NOT NULL,
        free_shipping INTEGER NOT NULL,
        new_publish_option TEXT,
        region TEXT,
        decision_mode TEXT NOT NULL,
        keyword_rules_json TEXT NOT NULL,
        is_running INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS result_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        result_filename TEXT NOT NULL,
        keyword TEXT NOT NULL,
        task_name TEXT NOT NULL,
        crawl_time TEXT NOT NULL,
        publish_time TEXT,
        price REAL,
        price_display TEXT,
        item_id TEXT,
        title TEXT,
        link TEXT,
        link_unique_key TEXT NOT NULL,
        seller_nickname TEXT,
        is_recommended INTEGER NOT NULL,
        analysis_source TEXT,
        keyword_hit_count INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        raw_json TEXT NOT NULL,
        UNIQUE(result_filename, link_unique_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS price_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword_slug TEXT NOT NULL,
        keyword TEXT NOT NULL,
        task_name TEXT NOT NULL,
        snapshot_time TEXT NOT NULL,
        snapshot_day TEXT NOT NULL,
        run_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        title TEXT,
        price REAL NOT NULL,
        price_display TEXT,
        tags_json TEXT NOT NULL,
        region TEXT,
        seller TEXT,
        publish_time TEXT,
        link TEXT,
        UNIQUE(keyword_slug, run_id, item_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trend_keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1,
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trend_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword_id INTEGER,
        keyword TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT '',
        snapshot_time TEXT NOT NULL,
        total_results INTEGER NOT NULL DEFAULT 0,
        new_items_24h INTEGER NOT NULL DEFAULT 0,
        new_items_3d INTEGER NOT NULL DEFAULT 0,
        seller_count INTEGER NOT NULL DEFAULT 0,
        new_seller_count INTEGER NOT NULL DEFAULT 0,
        min_price REAL,
        max_price REAL,
        median_price REAL,
        want_count_total INTEGER NOT NULL DEFAULT 0,
        want_count_avg REAL NOT NULL DEFAULT 0,
        title_terms_json TEXT NOT NULL DEFAULT '[]',
        title_repetition_rate REAL NOT NULL DEFAULT 0,
        same_image_count INTEGER NOT NULL DEFAULT 0,
        low_price_item_ratio REAL NOT NULL DEFAULT 0,
        opportunity_score REAL NOT NULL DEFAULT 0,
        opportunity_level TEXT NOT NULL DEFAULT 'D',
        growth_score REAL NOT NULL DEFAULT 0,
        competition_score REAL NOT NULL DEFAULT 0,
        profit_score REAL NOT NULL DEFAULT 0,
        freshness_score REAL NOT NULL DEFAULT 0,
        execution_score REAL NOT NULL DEFAULT 0,
        reasons_json TEXT NOT NULL DEFAULT '[]',
        action TEXT NOT NULL DEFAULT '',
        raw_metrics_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        FOREIGN KEY(keyword_id) REFERENCES trend_keywords(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trend_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        item_id TEXT,
        title TEXT NOT NULL DEFAULT '',
        price REAL,
        price_display TEXT,
        seller_nickname TEXT,
        want_count INTEGER NOT NULL DEFAULT 0,
        publish_time TEXT,
        link TEXT,
        image_key TEXT,
        raw_json TEXT NOT NULL DEFAULT '{}',
        link_unique_key TEXT NOT NULL,
        FOREIGN KEY(snapshot_id) REFERENCES trend_snapshots(id) ON DELETE CASCADE,
        UNIQUE(snapshot_id, link_unique_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trend_daily_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL,
        status TEXT NOT NULL,
        candidate_snapshot_ids_json TEXT NOT NULL DEFAULT '[]',
        ai_review_json TEXT NOT NULL DEFAULT '{}',
        push_title TEXT NOT NULL DEFAULT '',
        push_body TEXT NOT NULL DEFAULT '',
        push_channel TEXT NOT NULL DEFAULT 'bark',
        push_status TEXT NOT NULL DEFAULT 'pending',
        error_message TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        sent_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tasks_name ON tasks(task_name)",
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_crawl
    ON result_items(result_filename, crawl_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_publish
    ON result_items(result_filename, publish_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_price
    ON result_items(result_filename, price DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_recommended
    ON result_items(result_filename, is_recommended, analysis_source, crawl_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_snapshots_keyword_time
    ON price_snapshots(keyword_slug, snapshot_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_snapshots_keyword_item_time
    ON price_snapshots(keyword_slug, item_id, snapshot_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_trend_keywords_enabled_category
    ON trend_keywords(enabled, category, keyword)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_trend_snapshots_keyword_time
    ON trend_snapshots(keyword, snapshot_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_trend_snapshots_keyword_id_time
    ON trend_snapshots(keyword_id, snapshot_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_trend_snapshots_opportunity
    ON trend_snapshots(opportunity_level, opportunity_score DESC, snapshot_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_trend_items_snapshot
    ON trend_items(snapshot_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_trend_daily_reports_date
    ON trend_daily_reports(report_date DESC, id DESC)
    """,
)


def get_database_path() -> str:
    return os.getenv("APP_DATABASE_FILE", DEFAULT_DATABASE_PATH)


def _prepare_database_file(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")


def init_schema(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    _migrate_result_items_status(conn)
    conn.commit()


def _migrate_result_items_status(conn: sqlite3.Connection) -> None:
    """为 result_items 表添加 status 列（仅执行一次）。"""
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:result_items_status'"
    ).fetchone()
    if row is not None:
        return
    cols = [r[1] for r in conn.execute("PRAGMA table_info(result_items)").fetchall()]
    if "status" not in cols:
        conn.execute(
            "ALTER TABLE result_items ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
        )
    conn.execute(
        "INSERT OR REPLACE INTO app_metadata(key, value) VALUES ('migration:result_items_status', 'done')"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_results_filename_status_crawl"
        " ON result_items(result_filename, status, crawl_time DESC)"
    )


@contextmanager
def sqlite_connection(
    db_path: str | None = None,
) -> Iterator[sqlite3.Connection]:
    path = db_path or get_database_path()
    _prepare_database_file(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _apply_pragmas(conn)
        yield conn
    finally:
        conn.close()
