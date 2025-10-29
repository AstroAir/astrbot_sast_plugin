"""
AI summarization integration for Bilibili monitoring.

Handles AI-powered analysis and summarization of UP master videos.
"""
from __future__ import annotations

import os
from typing import Any

from utils.openrouter_client import ORSummaryOptions, summarize_batch
from models.bilibili import MonitorReport, VideoInfo


class AISummarizer:
    """AI-powered summarization for UP master videos."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "minimax/minimax-m2:free",
        prompt_template: str | None = None
    ):
        """Initialize AI summarizer.
        
        Args:
            api_key: OpenRouter API key (if None, will try to get from env)
            model: Model to use for summarization
            prompt_template: Custom prompt template
        """
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model
        self.prompt_template = prompt_template or self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """Get default prompt template."""
        return (
            "你是一个专业的 B 站内容分析助手。请分析以下 UP 主的最新视频信息，生成一份简洁的总结报告。\n\n"
            "要求：\n"
            "1. 总结视频的主要内容和亮点\n"
            "2. 分析视频数据（播放量、点赞等）的表现\n"
            "3. 提取关键信息点\n"
            "4. 保持客观、准确、易读\n\n"
            "请用中文输出，使用 Markdown 格式。"
        )

    def _format_video_info(self, video: VideoInfo) -> str:
        """Format video information for AI input.
        
        Args:
            video: Video information
            
        Returns:
            Formatted string
        """
        parts = [
            f"标题：{video.title}",
            f"链接：{video.get_url()}"
        ]

        if video.desc:
            parts.append(f"简介：{video.desc[:500]}")  # Limit description length

        if video.publish_time:
            pub_time = video.get_publish_datetime()
            if pub_time:
                parts.append(f"发布时间：{pub_time.strftime('%Y-%m-%d %H:%M')}")

        stats = []
        if video.play_count is not None:
            stats.append(f"播放 {self._format_number(video.play_count)}")
        if video.like_count is not None:
            stats.append(f"点赞 {self._format_number(video.like_count)}")
        if video.coin_count is not None:
            stats.append(f"投币 {self._format_number(video.coin_count)}")
        if video.favorite_count is not None:
            stats.append(f"收藏 {self._format_number(video.favorite_count)}")

        if stats:
            parts.append("数据：" + " | ".join(stats))

        return "\n".join(parts)

    def _format_number(self, num: int) -> str:
        """Format large numbers with units.
        
        Args:
            num: Number to format
            
        Returns:
            Formatted string (e.g., "1.2万", "3.5千")
        """
        if num >= 10000:
            return f"{num / 10000:.1f}万"
        elif num >= 1000:
            return f"{num / 1000:.1f}千"
        else:
            return str(num)

    def _build_summary_content(self, report: MonitorReport) -> str:
        """Build content for AI summarization.
        
        Args:
            report: Monitor report with videos
            
        Returns:
            Formatted content string
        """
        parts = [
            f"UP 主：{report.up_master_name} (mid: {report.up_master_mid})",
            f"检查时间：{report.check_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"新视频数量：{len(report.new_videos)}",
            "",
            "视频详情：",
            ""
        ]

        for idx, video in enumerate(report.new_videos, 1):
            parts.append(f"### 视频 {idx}")
            parts.append(self._format_video_info(video))
            parts.append("")

        return "\n".join(parts)

    async def summarize_report(self, report: MonitorReport) -> str | None:
        """Generate AI summary for a monitor report.
        
        Args:
            report: Monitor report to summarize
            
        Returns:
            AI-generated summary, or None if failed
        """
        if not self.api_key:
            return None

        if not report.has_new_videos():
            return None

        try:
            content = self._build_summary_content(report)

            # Prepare for summarization
            opts = ORSummaryOptions(
                api_key=self.api_key,
                model=self.model,
                language="zh"
            )

            # Build custom prompt
            full_content = f"{self.prompt_template}\n\n{content}"

            # Call AI summarization
            results = await summarize_batch(
                [(None, full_content)],
                opts
            )

            if results and len(results) > 0:
                summary = results[0].get("summary")
                if summary:
                    return summary

        except Exception:
            # If AI summarization fails, return None
            # The caller should handle this gracefully
            pass

        return None

    async def summarize_multiple_reports(
        self,
        reports: list[MonitorReport]
    ) -> dict[str, str]:
        """Generate AI summaries for multiple reports.
        
        Args:
            reports: List of monitor reports
            
        Returns:
            Dictionary mapping UP master mid to summary
        """
        summaries = {}

        for report in reports:
            if report.has_new_videos():
                summary = await self.summarize_report(report)
                if summary:
                    summaries[report.up_master_mid] = summary
                    report.ai_summary = summary

        return summaries

    def is_available(self) -> bool:
        """Check if AI summarization is available.
        
        Returns:
            True if API key is configured
        """
        return bool(self.api_key)

