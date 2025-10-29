"""
Utility functions and helpers for AstrBot SAST Plugin.

This package contains reusable utility functions including command parsing,
API clients, link extraction, and shared helper functions.
"""

from .command_utils import (
    parse_command_flags,
    extract_and_summarize_urls,
)
from .tavily_client import (
    TavilyOptions,
    extract_urls,
    tavily_extract,
)
from .openrouter_client import (
    ORSummaryOptions,
    summarize_batch,
)
from .link_extractor import (
    extract_bilibili_links,
    normalize_bilibili_url,
    extract_video_id,
    is_bilibili_url,
    deduplicate_links,
)
from .chart_generator import (
    ChartConfig,
    ChartGenerator,
    is_available as chart_available,
)

__all__ = [
    "parse_command_flags",
    "extract_and_summarize_urls",
    "TavilyOptions",
    "extract_urls",
    "tavily_extract",
    "ORSummaryOptions",
    "summarize_batch",
    "extract_bilibili_links",
    "normalize_bilibili_url",
    "extract_video_id",
    "is_bilibili_url",
    "deduplicate_links",
    "ChartConfig",
    "ChartGenerator",
    "chart_available",
]

