"""
Markdown formatting for Zhihu RSS feed reports.

Generates well-formatted Markdown documents from Zhihu monitor reports.
"""
from __future__ import annotations

from typing import Literal
from datetime import datetime

from models.zhihu import ZhihuMonitorReport, ZhihuFeedItem


class ZhihuFormatter:
    """Format Zhihu RSS monitor reports as Markdown documents."""

    def __init__(
        self,
        style: Literal["simple", "detailed", "compact"] = "detailed",
        include_bilibili_links: bool = True,
        include_summary: bool = True
    ):
        """
        Initialize Zhihu formatter.
        
        Args:
            style: Formatting style (simple, detailed, or compact)
            include_bilibili_links: Whether to highlight Bilibili links
            include_summary: Whether to include item summaries
        """
        self.style = style
        self.include_bilibili_links = include_bilibili_links
        self.include_summary = include_summary

    def _format_datetime(self, dt: datetime | None) -> str:
        """
        Format datetime for display.
        
        Args:
            dt: Datetime to format
            
        Returns:
            Formatted string
        """
        if dt is None:
            return "未知"
        return dt.strftime("%Y-%m-%d %H:%M")

    def _format_item_simple(self, item: ZhihuFeedItem, index: int) -> str:
        """
        Format item in simple style.
        
        Args:
            item: Feed item
            index: Item index (1-based)
            
        Returns:
            Formatted Markdown string
        """
        parts = [f"{index}. **{item.title}**"]
        
        if item.author:
            parts.append(f"   作者: {item.author}")
        
        parts.append(f"   🔗 {item.link}")
        
        if self.include_bilibili_links and item.bilibili_links:
            parts.append(f"   📺 B站视频: {len(item.bilibili_links)} 个")
        
        return "\n".join(parts)

    def _format_item_detailed(self, item: ZhihuFeedItem, index: int) -> str:
        """
        Format item in detailed style.
        
        Args:
            item: Feed item
            index: Item index (1-based)
            
        Returns:
            Formatted Markdown string
        """
        parts = [
            f"### {index}. {item.title}",
            ""
        ]
        
        if item.author:
            parts.append(f"👤 **作者**: {item.author}")
        
        parts.append(f"🔗 **链接**: {item.link}")
        
        if item.published:
            parts.append(f"📅 **发布时间**: {self._format_datetime(item.published)}")
        
        if self.include_summary and item.summary:
            # Limit summary length
            summary = item.summary[:300]
            if len(item.summary) > 300:
                summary += "..."
            parts.append(f"📝 **摘要**: {summary}")
        
        if self.include_bilibili_links and item.bilibili_links:
            parts.append("")
            parts.append(f"📺 **B站视频链接** ({len(item.bilibili_links)} 个):")
            for link in item.bilibili_links:
                parts.append(f"- {link}")
        
        parts.append("")
        return "\n".join(parts)

    def _format_item_compact_row(self, item: ZhihuFeedItem) -> list[str]:
        """
        Format item as table row for compact style.
        
        Args:
            item: Feed item
            
        Returns:
            List of cell values
        """
        bilibili_count = len(item.bilibili_links) if item.bilibili_links else 0
        bilibili_indicator = "✓" if bilibili_count > 0 else "-"
        
        return [
            f"[{item.title}]({item.link})",
            item.author or "-",
            self._format_datetime(item.published),
            f"{bilibili_count}" if bilibili_count > 0 else "-"
        ]

    def _format_items_compact(self, items: list[ZhihuFeedItem]) -> str:
        """
        Format items in compact table style.
        
        Args:
            items: List of feed items
            
        Returns:
            Formatted Markdown table
        """
        if not items:
            return ""

        # Table header
        if self.include_bilibili_links:
            lines = [
                "| 标题 | 作者 | 发布时间 | B站视频 |",
                "|------|------|----------|---------|"
            ]
        else:
            lines = [
                "| 标题 | 作者 | 发布时间 |",
                "|------|------|----------|"
            ]

        # Table rows
        for item in items:
            row = self._format_item_compact_row(item)
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def format_report(self, report: ZhihuMonitorReport) -> str:
        """
        Format a single Zhihu monitor report.
        
        Args:
            report: Monitor report to format
            
        Returns:
            Formatted Markdown string
        """
        if not report.has_new_items():
            return ""

        feed_name = report.feed_name or "Zhihu RSS"
        
        parts = [
            f"## 📰 {feed_name}",
            "",
            f"🔗 **订阅源**: {report.feed_url}",
            f"🆕 **新内容**: {len(report.new_items)} 条",
            f"🕐 **检查时间**: {self._format_datetime(report.check_time)}",
        ]
        
        # Add Bilibili link summary if applicable
        if self.include_bilibili_links and report.has_bilibili_links():
            bilibili_items = [item for item in report.new_items if item.bilibili_links]
            total_links = sum(len(item.bilibili_links) for item in bilibili_items)
            parts.append(f"📺 **包含B站视频**: {len(bilibili_items)} 条内容，共 {total_links} 个视频")
        
        parts.append("")
        parts.append("---")
        parts.append("")

        # Add items based on style
        if self.style == "simple":
            parts.append("### 内容列表")
            parts.append("")
            for idx, item in enumerate(report.new_items, 1):
                parts.append(self._format_item_simple(item, idx))
                parts.append("")

        elif self.style == "compact":
            parts.append("### 内容列表")
            parts.append("")
            parts.append(self._format_items_compact(report.new_items))
            parts.append("")

        else:  # detailed
            parts.append("### 内容详情")
            parts.append("")
            for idx, item in enumerate(report.new_items, 1):
                parts.append(self._format_item_detailed(item, idx))

        return "\n".join(parts)

    def format_multiple_reports(
        self,
        reports: list[ZhihuMonitorReport],
        title: str | None = None
    ) -> str:
        """
        Format multiple Zhihu monitor reports into a single document.
        
        Args:
            reports: List of monitor reports
            title: Optional document title
            
        Returns:
            Formatted Markdown string
        """
        # Filter reports with new items
        reports_with_items = [r for r in reports if r.has_new_items()]

        if not reports_with_items:
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
                "# 📰 知乎 RSS 更新报告",
                ""
            ])

        # Add summary
        total_items = sum(len(r.new_items) for r in reports_with_items)
        total_bilibili = sum(
            len([item for item in r.new_items if item.bilibili_links])
            for r in reports_with_items
        )
        
        parts.extend([
            f"📊 **统计**: {len(reports_with_items)} 个订阅源更新了 {total_items} 条内容",
        ])
        
        if self.include_bilibili_links and total_bilibili > 0:
            parts.append(f"📺 **B站视频**: {total_bilibili} 条内容包含 B站视频链接")
        
        parts.extend([
            f"🕐 **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            ""
        ])

        # Add each report
        for report in reports_with_items:
            parts.append(self.format_report(report))
            parts.append("")
            parts.append("---")
            parts.append("")

        return "\n".join(parts)

    def format_bilibili_links_only(self, reports: list[ZhihuMonitorReport]) -> str:
        """
        Format only the Bilibili links from reports.
        
        Args:
            reports: List of monitor reports
            
        Returns:
            Formatted Markdown string with only Bilibili links
        """
        reports_with_links = [r for r in reports if r.has_bilibili_links()]
        
        if not reports_with_links:
            return ""

        parts = [
            "# 📺 知乎内容中的 B站视频",
            ""
        ]

        for report in reports_with_links:
            feed_name = report.feed_name or "Zhihu RSS"
            parts.append(f"## {feed_name}")
            parts.append("")
            
            for item in report.new_items:
                if item.bilibili_links:
                    parts.append(f"### {item.title}")
                    parts.append(f"来源: {item.link}")
                    parts.append("")
                    for link in item.bilibili_links:
                        parts.append(f"- {link}")
                    parts.append("")

        return "\n".join(parts)

