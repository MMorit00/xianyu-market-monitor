"""
调度服务
负责管理定时任务的调度
"""
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Awaitable, Callable, List

from src.core.cron_utils import build_cron_trigger
from src.domain.models.task import Task
from src.infrastructure.config.env_manager import env_manager
from src.services.process_service import ProcessService


TREND_DAILY_REPORT_JOB_ID = "trend_daily_report"
TREND_DAILY_REPORT_DEFAULT_CRON = "0 9 * * *"


class SchedulerService:
    """调度服务"""

    def __init__(self, process_service: ProcessService):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self.process_service = process_service
        self.daily_report_runner: Callable[[], Awaitable[None]] | None = None

    def set_daily_report_runner(
        self,
        runner: Callable[[], Awaitable[None]] | None,
    ) -> None:
        """设置每日机会日报任务回调。"""
        self.daily_report_runner = runner

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            print("调度器已启动")

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("调度器已停止")

    def get_next_run_time(self, task_id: int):
        job = self.scheduler.get_job(f"task_{task_id}")
        if job is None:
            return None

        next_run_time = getattr(job, "next_run_time", None)
        if next_run_time is not None:
            return next_run_time

        trigger = getattr(job, "trigger", None)
        if trigger is None or not hasattr(trigger, "get_next_fire_time"):
            return None

        try:
            now = datetime.now(self.scheduler.timezone)
            return trigger.get_next_fire_time(None, now)
        except Exception:
            return None

    async def reload_jobs(self, tasks: List[Task]):
        """重新加载所有定时任务"""
        print("正在重新加载定时任务...")
        self.scheduler.remove_all_jobs()

        for task in tasks:
            if task.enabled and task.cron:
                try:
                    trigger = build_cron_trigger(
                        task.cron,
                        timezone=self.scheduler.timezone,
                    )
                    self.scheduler.add_job(
                        self._run_task,
                        trigger=trigger,
                        args=[task.id, task.task_name],
                        id=f"task_{task.id}",
                        name=f"Scheduled: {task.task_name}",
                        replace_existing=True
                    )
                    print(f"  -> 已为任务 '{task.task_name}' 添加定时规则: '{task.cron}'")
                except ValueError as e:
                    print(f"  -> [警告] 任务 '{task.task_name}' 的 Cron 表达式无效: {e}")

        self._add_daily_report_job()
        print("定时任务加载完成")

    async def _run_task(self, task_id: int, task_name: str):
        """执行定时任务"""
        print(f"定时任务触发: 正在为任务 '{task_name}' 启动爬虫...")
        await self.process_service.start_task(task_id, task_name)

    def _add_daily_report_job(self) -> None:
        if self.daily_report_runner is None:
            return
        enabled = str(
            env_manager.get_value("TREND_DAILY_REPORT_ENABLED", "true")
        ).strip().lower()
        if enabled not in {"1", "true", "yes", "y", "on"}:
            return
        cron = env_manager.get_value(
            "TREND_DAILY_REPORT_CRON",
            TREND_DAILY_REPORT_DEFAULT_CRON,
        )
        try:
            trigger = build_cron_trigger(cron, timezone=self.scheduler.timezone)
        except ValueError as exc:
            print(f"  -> [警告] 闲鱼机会日报 Cron 表达式无效: {exc}")
            return
        self.scheduler.add_job(
            self._run_daily_report,
            trigger=trigger,
            id=TREND_DAILY_REPORT_JOB_ID,
            name="Scheduled: 闲鱼机会日报",
            replace_existing=True,
        )
        print(f"  -> 已添加闲鱼机会日报定时规则: '{cron}'")

    async def _run_daily_report(self):
        """执行每日 AI 闲鱼机会日报。"""
        if self.daily_report_runner is None:
            return
        print("定时任务触发: 正在生成闲鱼 AI 机会日报...")
        try:
            await self.daily_report_runner()
        except Exception as exc:
            print(f"闲鱼 AI 机会日报生成失败: {exc}")
