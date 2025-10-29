"""
Core business logic for AstrBot SAST Plugin.

This package contains the core functionality for Bilibili and Zhihu monitoring,
including API clients, monitoring logic, and state management.
"""

from .bilibili_api import (
    BilibiliDescription,
    get_bilibili_description,
    fetch_archives,
    pick_latest_from_archives,
)
from .monitor import BilibiliMonitor
from .state import StateManager
from .zhihu_rss import ZhihuRSSClient, get_reports_with_new_items, get_reports_with_bilibili_links
from .zhihu_state import ZhihuStateManager
from .scheduler import SchedulerManager, TaskConfig, TaskStatus

__all__ = [
    # Bilibili
    "BilibiliDescription",
    "get_bilibili_description",
    "fetch_archives",
    "pick_latest_from_archives",
    "BilibiliMonitor",
    "StateManager",
    # Zhihu
    "ZhihuRSSClient",
    "ZhihuStateManager",
    "get_reports_with_new_items",
    "get_reports_with_bilibili_links",
    # Scheduler
    "SchedulerManager",
    "TaskConfig",
    "TaskStatus",
]

