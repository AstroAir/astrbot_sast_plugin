"""
AI-powered daily report generation service.

Generates comprehensive daily reports with AI summaries, trending topics,
visualizations, and multiple output formats.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from models.report import DailyReport, DailyReportConfig, ContentCategory, CategorySection
from utils.openrouter_client import summarize_batch, ORSummaryOptions
from utils.chart_generator import ChartGenerator, ChartConfig, is_available as chart_available


logger = logging.getLogger(__name__)


class DailyReportGenerator:
    """Generates AI-powered daily reports from aggregated content with visualizations."""

    def __init__(
        self,
        openrouter_api_key: str | None = None,
        enable_ai: bool = True,
        chart_config: ChartConfig | None = None
    ):
        """
        Initialize daily report generator.

        Args:
            openrouter_api_key: OpenRouter API key for AI summaries
            enable_ai: Whether to enable AI features
            chart_config: Configuration for chart generation
        """
        self.openrouter_api_key = openrouter_api_key
        self.enable_ai = enable_ai and openrouter_api_key is not None

        # Initialize chart generator if available and enabled
        self.chart_generator: ChartGenerator | None = None
        if chart_config and chart_config.enabled and chart_available():
            try:
                self.chart_generator = ChartGenerator(chart_config)
                logger.info("Chart generation enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize chart generator: {e}")
        elif chart_config and chart_config.enabled and not chart_available():
            logger.warning("Chart generation requested but matplotlib not available")

        if not self.enable_ai:
            logger.warning("AI features disabled (no API key provided)")
    
    async def generate_section_summary(self, section: CategorySection) -> str | None:
        """
        Generate AI summary for a category section.
        
        Args:
            section: Category section to summarize
            
        Returns:
            AI-generated summary or None if AI disabled
        """
        if not self.enable_ai or not self.openrouter_api_key:
            return None
        
        if not section.items:
            return None
        
        # Prepare content for summarization
        content_texts = []
        for item in section.items[:5]:  # Limit to top 5 items
            text = f"标题: {item.title}\n"
            if item.summary:
                text += f"摘要: {item.summary}\n"
            content_texts.append(text)
        
        combined_text = "\n\n".join(content_texts)
        
        # Generate summary
        try:
            options = ORSummaryOptions(
                api_key=self.openrouter_api_key,
                max_tokens=200,
                temperature=0.7
            )
            
            prompt = f"请为以下{section.category.value}类别的内容生成一个简洁的总结（100字以内）：\n\n{combined_text}"
            
            results = await summarize_batch([prompt], options)
            if results and results[0]:
                return results[0]
        except Exception as e:
            logger.error(f"Failed to generate section summary: {e}")
        
        return None
    
    async def generate_executive_summary(self, report: DailyReport) -> str | None:
        """
        Generate executive summary for the entire report.
        
        Args:
            report: Daily report
            
        Returns:
            AI-generated executive summary or None if AI disabled
        """
        if not self.enable_ai or not self.openrouter_api_key:
            return None
        
        if report.total_items == 0:
            return None
        
        # Prepare overview
        overview = f"今日共收集 {report.total_items} 条内容"
        if report.bilibili_items > 0:
            overview += f"，其中 B站视频 {report.bilibili_items} 个"
        if report.zhihu_items > 0:
            overview += f"，知乎内容 {report.zhihu_items} 条"
        overview += "。\n\n"
        
        # Add top items from each category
        category_summaries = []
        for section in report.sections:
            if section.items:
                top_item = section.items[0]
                category_summaries.append(
                    f"{section.category.value}: {top_item.title}"
                )
        
        combined_text = overview + "\n".join(category_summaries)
        
        # Generate summary
        try:
            options = ORSummaryOptions(
                api_key=self.openrouter_api_key,
                max_tokens=300,
                temperature=0.7
            )
            
            prompt = f"请为以下每日内容汇总生成一个执行摘要（150字以内），突出重点和趋势：\n\n{combined_text}"
            
            results = await summarize_batch([prompt], options)
            if results and results[0]:
                return results[0]
        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
        
        return None
    
    async def extract_trending_topics(self, report: DailyReport) -> list[str]:
        """
        Extract trending topics from report content.
        
        Args:
            report: Daily report
            
        Returns:
            List of trending topics
        """
        # Simple keyword extraction (could be enhanced with AI)
        word_freq: dict[str, int] = {}
        
        for item in report.get_all_items():
            # Extract words from title
            words = item.title.split()
            for word in words:
                if len(word) >= 2:  # Ignore single characters
                    word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top trending words
        trending = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in trending[:10]]
    
    async def enhance_report(
        self,
        report: DailyReport,
        config: DailyReportConfig
    ) -> DailyReport:
        """
        Enhance report with AI-generated content.
        
        Args:
            report: Daily report to enhance
            config: Report configuration
            
        Returns:
            Enhanced report
        """
        # Generate section summaries
        if config.generate_ai_summary:
            for section in report.sections:
                section.ai_summary = await self.generate_section_summary(section)
        
        # Generate executive summary
        if config.generate_ai_summary:
            report.executive_summary = await self.generate_executive_summary(report)
        
        # Extract trending topics
        if config.include_trending:
            report.trending_topics = await self.extract_trending_topics(report)
        
        return report
    
    def format_markdown(self, report: DailyReport, config: DailyReportConfig) -> str:
        """
        Format report as Markdown.
        
        Args:
            report: Daily report
            config: Report configuration
            
        Returns:
            Markdown-formatted report
        """
        lines = [
            f"# {report.title}",
            "",
            f"📅 **日期**: {report.report_date.strftime('%Y年%m月%d日')}",
            f"🕐 **生成时间**: {report.generation_time.strftime('%H:%M:%S') if report.generation_time else 'N/A'}",
            ""
        ]
        
        # Statistics
        if config.include_statistics:
            lines.extend([
                "## 📊 统计信息",
                "",
                f"- 📝 总内容数: {report.total_items}",
                f"- 📺 B站视频: {report.bilibili_items}",
                f"- 📰 知乎内容: {report.zhihu_items}",
                f"- 📂 分类数: {len(report.sections)}",
                ""
            ])
        
        # Executive summary
        if report.executive_summary:
            lines.extend([
                "## 📋 执行摘要",
                "",
                report.executive_summary,
                ""
            ])
        
        # Trending topics
        if config.include_trending and report.trending_topics:
            lines.extend([
                "## 🔥 热门话题",
                "",
                " · ".join(f"`{topic}`" for topic in report.trending_topics[:10]),
                ""
            ])
        
        lines.append("---\n")
        
        # Category sections
        for section in report.sections:
            if not section.items:
                continue
            
            category_name = {
                ContentCategory.TECHNOLOGY: "💻 技术",
                ContentCategory.ENTERTAINMENT: "🎮 娱乐",
                ContentCategory.EDUCATION: "📚 教育",
                ContentCategory.NEWS: "📰 新闻",
                ContentCategory.LIFESTYLE: "🌟 生活",
                ContentCategory.OTHER: "📌 其他"
            }.get(section.category, section.category.value)
            
            lines.extend([
                f"## {category_name}",
                ""
            ])
            
            # Section AI summary
            if section.ai_summary:
                lines.extend([
                    f"**AI 总结**: {section.ai_summary}",
                    ""
                ])
            
            # Items
            for idx, item in enumerate(section.items, 1):
                # Highlight important items
                if config.highlight_important and item.importance_score >= 0.7:
                    lines.append(f"### ⭐ {idx}. {item.title}")
                else:
                    lines.append(f"### {idx}. {item.title}")
                
                lines.append("")
                
                if item.author:
                    lines.append(f"👤 **作者**: {item.author}")
                
                lines.append(f"🔗 **链接**: {item.url}")
                
                if item.published:
                    lines.append(f"📅 **发布**: {item.published.strftime('%Y-%m-%d %H:%M')}")
                
                if item.summary:
                    lines.append(f"📝 **摘要**: {item.summary}")
                
                # Source-specific data
                if item.source.value == "bilibili":
                    view_count = item.source_data.get('view_count')
                    like_count = item.source_data.get('like_count')
                    if view_count or like_count:
                        stats = []
                        if view_count:
                            stats.append(f"👁️ {view_count}")
                        if like_count:
                            stats.append(f"👍 {like_count}")
                        lines.append(f"📊 **数据**: {' · '.join(stats)}")
                
                elif item.source.value == "zhihu":
                    bilibili_links = item.source_data.get('bilibili_links', [])
                    if bilibili_links:
                        lines.append(f"📺 **包含B站视频**: {len(bilibili_links)} 个")
                
                lines.extend(["", "---", ""])
        
        return "\n".join(lines)
    
    def format_text(self, report: DailyReport, config: DailyReportConfig) -> str:
        """
        Format report as plain text.
        
        Args:
            report: Daily report
            config: Report configuration
            
        Returns:
            Plain text formatted report
        """
        # Simple text version (strip markdown formatting)
        markdown = self.format_markdown(report, config)
        
        # Remove markdown syntax
        text = markdown.replace('#', '').replace('**', '').replace('`', '')
        text = text.replace('---', '=' * 50)
        
        return text
    
    async def generate_charts(self, report: DailyReport) -> dict[str, str | bytes]:
        """
        Generate all charts for the report.

        Args:
            report: Daily report

        Returns:
            Dictionary mapping chart names to chart data (bytes or base64 string)
        """
        if not self.chart_generator:
            return {}

        try:
            charts = await self.chart_generator.generate_all_charts(report)
            logger.info(f"Generated {len(charts)} charts for daily report")
            return charts
        except Exception as e:
            logger.error(f"Failed to generate charts: {e}")
            return {}

    async def generate(
        self,
        report: DailyReport,
        config: DailyReportConfig,
        include_charts: bool = False
    ) -> str | tuple[str, dict[str, str | bytes]]:
        """
        Generate formatted daily report.

        Args:
            report: Daily report
            config: Report configuration
            include_charts: Whether to generate and return charts

        Returns:
            Formatted report string, or tuple of (report, charts) if include_charts=True
        """
        # Enhance with AI
        if config.generate_ai_summary:
            report = await self.enhance_report(report, config)

        # Generate charts if requested
        charts = {}
        if include_charts and self.chart_generator:
            charts = await self.generate_charts(report)

        # Format based on output format
        if config.output_format == "markdown":
            formatted = self.format_markdown(report, config)
        elif config.output_format == "text":
            formatted = self.format_text(report, config)
        else:
            # Default to markdown
            formatted = self.format_markdown(report, config)

        # Return with or without charts
        if include_charts:
            return formatted, charts
        else:
            return formatted

