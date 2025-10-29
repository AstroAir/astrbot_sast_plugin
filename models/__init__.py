"""
Data models for AstrBot SAST Plugin.

This package contains all data models used throughout the plugin,
including configuration models, video information, and monitoring reports.
"""

from .bilibili import (
    UPMasterConfig,
    VideoInfo,
    UPMasterState,
    MonitorState,
    MonitorReport,
)

from .zhihu import (
    ZhihuFeedItem,
    ZhihuFeedConfig,
    ZhihuFeedState,
    ZhihuMonitorState,
    ZhihuMonitorReport,
)

from .report import (
    ContentSource,
    ContentCategory,
    ContentItem,
    CategorySection,
    DailyReportConfig,
    DailyReport,
)

__all__ = [
    # Bilibili models
    "UPMasterConfig",
    "VideoInfo",
    "UPMasterState",
    "MonitorState",
    "MonitorReport",
    # Zhihu models
    "ZhihuFeedItem",
    "ZhihuFeedConfig",
    "ZhihuFeedState",
    "ZhihuMonitorState",
    "ZhihuMonitorReport",
    # Report models
    "ContentSource",
    "ContentCategory",
    "ContentItem",
    "CategorySection",
    "DailyReportConfig",
    "DailyReport",
]

