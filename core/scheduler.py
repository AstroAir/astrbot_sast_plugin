"""
Advanced scheduling system for AstrBot SAST Plugin.

Provides cron-like scheduling, task monitoring, and error recovery using APScheduler.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Callable, Any, Awaitable
from dataclasses import dataclass, field

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False


logger = logging.getLogger(__name__)


@dataclass
class TaskConfig:
    """Configuration for a scheduled task."""
    
    task_id: str
    name: str
    func: Callable[[], Awaitable[Any]]
    enabled: bool = True
    
    # Scheduling options (use one)
    cron: str | None = None  # Cron expression (e.g., "0 9 * * *" for 9 AM daily)
    interval_minutes: int | None = None  # Interval in minutes
    interval_hours: int | None = None  # Interval in hours
    run_at: datetime | None = None  # One-time execution at specific time
    
    # Error handling
    max_retries: int = 3
    retry_delay_seconds: int = 60
    exponential_backoff: bool = True
    
    # Metadata
    description: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class TaskStatus:
    """Status information for a scheduled task."""
    
    task_id: str
    name: str
    enabled: bool
    next_run_time: datetime | None
    last_run_time: datetime | None
    last_success_time: datetime | None
    last_error: str | None
    error_count: int = 0
    total_runs: int = 0
    successful_runs: int = 0


class SchedulerManager:
    """
    Manages scheduled tasks with advanced features.
    
    Provides cron-like scheduling, error recovery, and task monitoring.
    """
    
    def __init__(self, use_apscheduler: bool = True):
        """
        Initialize scheduler manager.
        
        Args:
            use_apscheduler: Whether to use APScheduler (falls back to simple loop if False)
        """
        self.use_apscheduler = use_apscheduler and APSCHEDULER_AVAILABLE
        self.scheduler: AsyncIOScheduler | None = None
        self.tasks: dict[str, TaskConfig] = {}
        self.task_status: dict[str, TaskStatus] = {}
        self.simple_tasks: dict[str, asyncio.Task] = {}  # For fallback mode
        self.is_running = False
        
        if self.use_apscheduler:
            self.scheduler = AsyncIOScheduler()
            self.scheduler.add_listener(
                self._on_job_executed,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
            )
        else:
            logger.warning(
                "APScheduler not available. Falling back to simple interval-based scheduling. "
                "Install APScheduler for advanced scheduling features: pip install apscheduler"
            )
    
    async def start(self):
        """Start the scheduler."""
        if self.is_running:
            return
        
        self.is_running = True
        
        if self.use_apscheduler and self.scheduler:
            self.scheduler.start()
            logger.info("APScheduler started")
        else:
            logger.info("Simple scheduler started")
    
    async def stop(self):
        """Stop the scheduler and all tasks."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.use_apscheduler and self.scheduler:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped")
        else:
            # Cancel all simple tasks
            for task in self.simple_tasks.values():
                if not task.done():
                    task.cancel()
            self.simple_tasks.clear()
            logger.info("Simple scheduler stopped")
    
    def add_task(self, config: TaskConfig):
        """
        Add a scheduled task.
        
        Args:
            config: Task configuration
        """
        self.tasks[config.task_id] = config
        self.task_status[config.task_id] = TaskStatus(
            task_id=config.task_id,
            name=config.name,
            enabled=config.enabled,
            next_run_time=None,
            last_run_time=None,
            last_success_time=None,
            last_error=None
        )
        
        if not config.enabled:
            logger.info(f"Task '{config.name}' added but disabled")
            return
        
        if self.use_apscheduler and self.scheduler:
            self._add_apscheduler_job(config)
        else:
            self._add_simple_task(config)
    
    def _add_apscheduler_job(self, config: TaskConfig):
        """Add job to APScheduler."""
        if not self.scheduler:
            return
        
        # Determine trigger
        trigger = None
        if config.cron:
            # Parse cron expression
            parts = config.cron.split()
            if len(parts) == 5:
                trigger = CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4]
                )
        elif config.interval_minutes:
            trigger = IntervalTrigger(minutes=config.interval_minutes)
        elif config.interval_hours:
            trigger = IntervalTrigger(hours=config.interval_hours)
        elif config.run_at:
            trigger = DateTrigger(run_date=config.run_at)
        
        if trigger:
            self.scheduler.add_job(
                self._execute_task_with_retry,
                trigger=trigger,
                args=[config.task_id],
                id=config.task_id,
                name=config.name,
                replace_existing=True
            )
            logger.info(f"Task '{config.name}' scheduled with APScheduler")
    
    def _add_simple_task(self, config: TaskConfig):
        """Add task using simple asyncio loop (fallback)."""
        if config.interval_minutes:
            interval = config.interval_minutes * 60
        elif config.interval_hours:
            interval = config.interval_hours * 3600
        else:
            logger.warning(f"Task '{config.name}' requires interval for simple scheduler")
            return
        
        async def task_loop():
            while self.is_running:
                try:
                    await self._execute_task_with_retry(config.task_id)
                except Exception as e:
                    logger.error(f"Error in task loop '{config.name}': {e}")
                
                await asyncio.sleep(interval)
        
        task = asyncio.create_task(task_loop())
        self.simple_tasks[config.task_id] = task
        logger.info(f"Task '{config.name}' scheduled with simple scheduler (interval: {interval}s)")
    
    async def _execute_task_with_retry(self, task_id: str):
        """Execute task with retry logic."""
        config = self.tasks.get(task_id)
        status = self.task_status.get(task_id)
        
        if not config or not status:
            return
        
        status.last_run_time = datetime.now()
        status.total_runs += 1
        
        retry_count = 0
        last_error = None
        
        while retry_count <= config.max_retries:
            try:
                await config.func()
                
                # Success
                status.last_success_time = datetime.now()
                status.successful_runs += 1
                status.last_error = None
                status.error_count = 0
                logger.info(f"Task '{config.name}' completed successfully")
                return
                
            except Exception as e:
                last_error = str(e)
                retry_count += 1
                
                if retry_count <= config.max_retries:
                    # Calculate delay with exponential backoff
                    delay = config.retry_delay_seconds
                    if config.exponential_backoff:
                        delay = delay * (2 ** (retry_count - 1))
                    
                    logger.warning(
                        f"Task '{config.name}' failed (attempt {retry_count}/{config.max_retries + 1}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Task '{config.name}' failed after {config.max_retries + 1} attempts: {e}")
        
        # All retries failed
        status.last_error = last_error
        status.error_count += 1
    
    def _on_job_executed(self, event: JobExecutionEvent):
        """Handle job execution events from APScheduler."""
        task_id = event.job_id
        status = self.task_status.get(task_id)
        
        if status and self.scheduler:
            job = self.scheduler.get_job(task_id)
            if job:
                status.next_run_time = job.next_run_time
    
    def remove_task(self, task_id: str):
        """Remove a scheduled task."""
        if task_id in self.tasks:
            del self.tasks[task_id]
        
        if task_id in self.task_status:
            del self.task_status[task_id]
        
        if self.use_apscheduler and self.scheduler:
            self.scheduler.remove_job(task_id)
        elif task_id in self.simple_tasks:
            task = self.simple_tasks[task_id]
            if not task.done():
                task.cancel()
            del self.simple_tasks[task_id]
        
        logger.info(f"Task '{task_id}' removed")
    
    def get_task_status(self, task_id: str) -> TaskStatus | None:
        """Get status of a specific task."""
        return self.task_status.get(task_id)
    
    def get_all_task_status(self) -> list[TaskStatus]:
        """Get status of all tasks."""
        return list(self.task_status.values())
    
    def enable_task(self, task_id: str):
        """Enable a disabled task."""
        config = self.tasks.get(task_id)
        status = self.task_status.get(task_id)
        
        if config and status:
            config.enabled = True
            status.enabled = True
            
            if self.use_apscheduler:
                self._add_apscheduler_job(config)
            else:
                self._add_simple_task(config)
            
            logger.info(f"Task '{config.name}' enabled")
    
    def disable_task(self, task_id: str):
        """Disable a task without removing it."""
        config = self.tasks.get(task_id)
        status = self.task_status.get(task_id)
        
        if config and status:
            config.enabled = False
            status.enabled = False
            
            if self.use_apscheduler and self.scheduler:
                self.scheduler.pause_job(task_id)
            elif task_id in self.simple_tasks:
                task = self.simple_tasks[task_id]
                if not task.done():
                    task.cancel()
                del self.simple_tasks[task_id]
            
            logger.info(f"Task '{config.name}' disabled")

