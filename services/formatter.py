"""
Markdown formatting for Bilibili monitoring reports.

Generates well-formatted Markdown documents from monitor reports.
"""
from __future__ import annotations

from typing import Literal
from datetime import datetime

from models.bilibili import MonitorReport, VideoInfo


class MarkdownFormatter:
    """Format monitor reports as Markdown documents."""

    def __init__(
        self,
        style: Literal["simple", "detailed", "compact"] = "detailed",
        include_stats: bool = True
    ):
        """Initialize Markdown formatter.
        
        Args:
            style: Formatting style (simple, detailed, or compact)
            include_stats: Whether to include video statistics
        """
        self.style = style
        self.include_stats = include_stats

    def _format_number(self, num: int | None) -> str:
        """Format large numbers with units.
        
        Args:
            num: Number to format
            
        Returns:
            Formatted string
        """
        if num is None:
            return "-"

        if num >= 10000:
            return f"{num / 10000:.1f}万"
        elif num >= 1000:
            return f"{num / 1000:.1f}千"
        else:
            return str(num)

    def _format_datetime(self, dt: datetime | None) -> str:
        """Format datetime for display.
        
        Args:
            dt: Datetime to format
            
        Returns:
            Formatted string
        """
        if dt is None:
            return "未知"
        return dt.strftime("%Y-%m-%d %H:%M")

    def _format_video_simple(self, video: VideoInfo, index: int) -> str:
        """Format video in simple style.
        
        Args:
            video: Video information
            index: Video index (1-based)
            
        Returns:
            Formatted Markdown string
        """
        parts = [
            f"{index}. **{video.title}**",
            f"   🔗 {video.get_url()}"
        ]
        return "\n".join(parts)

    def _format_video_detailed(self, video: VideoInfo, index: int) -> str:
        """Format video in detailed style.
        
        Args:
            video: Video information
            index: Video index (1-based)
            
        Returns:
            Formatted Markdown string
        """
        parts = [
            f"### {index}. {video.title}",
            "",
            f"🔗 **链接**: {video.get_url()}",
        ]

        if video.desc:
            # Limit description length
            desc = video.desc[:200]
            if len(video.desc) > 200:
                desc += "..."
            parts.append(f"📝 **简介**: {desc}")

        pub_time = video.get_publish_datetime()
        if pub_time:
            parts.append(f"📅 **发布时间**: {self._format_datetime(pub_time)}")

        if self.include_stats:
            stats = []
            if video.play_count is not None:
                stats.append(f"▶️ 播放 {self._format_number(video.play_count)}")
            if video.like_count is not None:
                stats.append(f"👍 点赞 {self._format_number(video.like_count)}")
            if video.coin_count is not None:
                stats.append(f"🪙 投币 {self._format_number(video.coin_count)}")
            if video.favorite_count is not None:
                stats.append(f"⭐ 收藏 {self._format_number(video.favorite_count)}")

            if stats:
                parts.append(f"📊 **数据**: {' | '.join(stats)}")

        parts.append("")
        return "\n".join(parts)

    def _format_video_compact_row(self, video: VideoInfo) -> list[str]:
        """Format video as table row for compact style.
        
        Args:
            video: Video information
            
        Returns:
            List of cell values
        """
        pub_time = video.get_publish_datetime()
        return [
            f"[{video.title}]({video.get_url()})",
            self._format_datetime(pub_time),
            self._format_number(video.play_count) if self.include_stats else "-",
            self._format_number(video.like_count) if self.include_stats else "-"
        ]

    def _format_videos_compact(self, videos: list[VideoInfo]) -> str:
        """Format videos in compact table style.
        
        Args:
            videos: List of videos
            
        Returns:
            Formatted Markdown table
        """
        if not videos:
            return ""

        # Table header
        if self.include_stats:
            lines = [
                "| 标题 | 发布时间 | 播放 | 点赞 |",
                "|------|----------|------|------|"
            ]
        else:
            lines = [
                "| 标题 | 发布时间 |",
                "|------|----------|"
            ]

        # Table rows
        for video in videos:
            row = self._format_video_compact_row(video)
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def format_report(self, report: MonitorReport) -> str:
        """Format a single monitor report.
        
        Args:
            report: Monitor report to format
            
        Returns:
            Formatted Markdown string
        """
        if not report.has_new_videos():
            return ""

        parts = [
            f"## 📺 {report.up_master_name}",
            "",
            f"🆔 **UP 主 ID**: {report.up_master_mid}",
            f"🆕 **新视频数**: {len(report.new_videos)}",
            f"🕐 **检查时间**: {self._format_datetime(report.check_time)}",
            ""
        ]

        # Add AI summary if available
        if report.ai_summary:
            parts.extend([
                "### 🤖 AI 总结",
                "",
                report.ai_summary,
                "",
                "---",
                ""
            ])

        # Add videos based on style
        if self.style == "simple":
            parts.append("### 视频列表")
            parts.append("")
            for idx, video in enumerate(report.new_videos, 1):
                parts.append(self._format_video_simple(video, idx))
                parts.append("")

        elif self.style == "compact":
            parts.append("### 视频列表")
            parts.append("")
            parts.append(self._format_videos_compact(report.new_videos))
            parts.append("")

        else:  # detailed
            parts.append("### 视频详情")
            parts.append("")
            for idx, video in enumerate(report.new_videos, 1):
                parts.append(self._format_video_detailed(video, idx))

        return "\n".join(parts)

    def format_multiple_reports(
        self,
        reports: list[MonitorReport],
        title: str | None = None
    ) -> str:
        """Format multiple monitor reports into a single document.
        
        Args:
            reports: List of monitor reports
            title: Optional document title
            
        Returns:
            Formatted Markdown string
        """
        # Filter reports with new videos
        reports_with_videos = [r for r in reports if r.has_new_videos()]

        if not reports_with_videos:
            return ""

        parts = []

        # Add title
        if title:
            parts.extend([
                f"# {title}",
                ""
            ])
        else:
            parts.extend([
                "# 📺 B站 UP 主更新报告",
                ""
            ])

        # Add summary
        total_videos = sum(len(r.new_videos) for r in reports_with_videos)
        parts.extend([
            f"📊 **统计**: {len(reports_with_videos)} 位 UP 主更新了 {total_videos} 个视频",
            f"🕐 **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            ""
        ])

        # Add each report
        for report in reports_with_videos:
            parts.append(self.format_report(report))
            parts.append("")
            parts.append("---")
            parts.append("")

        return "\n".join(parts)

    def format_summary_only(self, report: MonitorReport) -> str:
        """Format only the AI summary part of a report.
        
        Args:
            report: Monitor report
            
        Returns:
            Formatted Markdown string with only summary
        """
        if not report.ai_summary:
            return ""

        parts = [
            f"## 📺 {report.up_master_name}",
            "",
            report.ai_summary,
            ""
        ]

        return "\n".join(parts)

