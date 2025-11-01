"""
AstrBot SAST Plugin - Content Monitoring & Analysis

Provides comprehensive content monitoring and analysis tools including:
- Bilibili video tools (description fetching, link extraction, AI summarization)
- UP master monitoring with new video detection
- Zhihu RSS feed monitoring with Bilibili link extraction
- Advanced scheduling with cron support
- AI-powered daily reports with content aggregation
"""
from astrbot.api.event import filter, AstrMessageEvent, MessageChain  # type: ignore
from astrbot.api.star import Context, Star, register  # type: ignore
from astrbot.api import logger  # type: ignore

import os
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

# Core modules
from core.bilibili_api import (
    get_bilibili_description,
    fetch_archives,
    pick_latest_from_archives,
)
from core.state import StateManager
from core.monitor import BilibiliMonitor
from core.zhihu_rss import ZhihuRSSClient
from core.zhihu_state import ZhihuStateManager
from core.scheduler import SchedulerManager, TaskConfig

# Models
from models.bilibili import UPMasterConfig
from models.zhihu import ZhihuFeedConfig
from models.report import DailyReportConfig

# Services
from services.ai_summarizer import AISummarizer
from services.formatter import MarkdownFormatter
from services.zhihu_formatter import ZhihuFormatter
from services.report_aggregator import ReportAggregator
from services.daily_report import DailyReportGenerator
from services.content_search import ContentSearchEngine, SearchQuery
from services.export_service import ReportExporter
from services.archive_service import ArchiveManager

# Utilities
from utils.command_utils import (
    parse_command_flags,
    extract_and_summarize_urls,
)
from utils.chart_generator import ChartConfig, is_available as chart_available


@register("astrbot-sast", "AstroAir", "内容监控与分析工具集 (Bilibili/Zhihu/AI报告)", "2.0.0")
class SASTPlugin(Star):
    """
    AstrBot SAST Plugin - Content Monitoring & Analysis

    Provides comprehensive content monitoring and analysis:
    - /bili_desc: Get video description and optionally extract/summarize links
    - /bili_latest: Get latest video from a user and optionally extract/summarize links
    - /bili_monitor: Manually trigger monitoring check for configured UP masters
    - /zhihu_check: Manually trigger Zhihu RSS feed check
    - /daily_report: Manually generate daily content report with AI summaries and charts
    - /search: Search through monitored content with keyword search
    - /filter: Filter monitored content by category, source, importance, and date
    - /export: Export daily reports in multiple formats (JSON, Markdown, HTML)
    - /archive: Manage report archives (list, view, delete)

    Background tasks:
    - Bilibili UP master monitoring
    - Zhihu RSS feed monitoring
    - Daily report generation
    """

    def __init__(self, context: Context):
        super().__init__(context)

        # Get configuration from context
        self.config: dict[str, Any] = {}
        if hasattr(context, 'config_helper') and context.config_helper:
            self.config = context.config_helper.get_all() or {}

        # Initialize Bilibili monitoring components
        self.bili_state_file = Path("data") / "bili_monitor_state.json"
        self.bili_state_manager = StateManager(self.bili_state_file)
        self.bili_monitor = BilibiliMonitor(self.bili_state_manager)

        # Initialize Zhihu monitoring components
        self.zhihu_state_file = Path("data") / "zhihu_monitor_state.json"
        self.zhihu_state_manager = ZhihuStateManager(self.zhihu_state_file)
        self.zhihu_client = ZhihuRSSClient()

        # Initialize service components
        self.ai_summarizer: AISummarizer | None = None
        self.bili_formatter: MarkdownFormatter | None = None
        self.zhihu_formatter: ZhihuFormatter | None = None
        self.report_aggregator: ReportAggregator | None = None
        self.daily_report_generator: DailyReportGenerator | None = None
        self.search_engine: ContentSearchEngine = ContentSearchEngine()
        self.report_exporter: ReportExporter = ReportExporter()
        self.archive_manager: ArchiveManager = ArchiveManager()

        # Scheduler
        self.scheduler: SchedulerManager | None = None

        # Legacy timer task (for fallback)
        self.monitor_task: asyncio.Task | None = None
        self.is_running = False

        # Start monitoring if enabled (delayed to after initialize)
        if self.config.get("enabled", False):
            use_scheduler = self.config.get("use_advanced_scheduler", False)
            if use_scheduler:
                asyncio.create_task(self._start_scheduler())
            else:
                asyncio.create_task(self._start_monitoring())

    async def initialize(self):
        """Initialize plugin components."""
        logger.info("内容监控与分析插件已初始化")

        # Initialize AI summarizer if enabled
        if self.config.get("ai_summary_enabled", True):
            api_key = self.config.get("openrouter_api_key") or os.environ.get("OPENROUTER_API_KEY")
            if api_key:
                self.ai_summarizer = AISummarizer(
                    api_key=api_key,
                    model=self.config.get("openrouter_model", "minimax/minimax-m2:free"),
                    prompt_template=self.config.get("ai_prompt_template")
                )
                logger.info("AI 总结功能已启用")

        # Initialize formatters
        self.bili_formatter = MarkdownFormatter(
            style=self.config.get("markdown_style", "detailed"),
            include_stats=self.config.get("include_video_stats", True)
        )
        self.zhihu_formatter = ZhihuFormatter(
            style=self.config.get("markdown_style", "detailed")
        )

        # Initialize report components
        self.report_aggregator = ReportAggregator()

        # Initialize chart configuration
        chart_config = None
        if self.config.get("chart_enabled", True) and chart_available():
            chart_config = ChartConfig(
                enabled=True,
                output_format=self.config.get("chart_output_format", "png"),
                dpi=self.config.get("chart_dpi", 100),
                figsize=tuple(self.config.get("chart_figsize", [10, 6])),
                style=self.config.get("chart_style", "seaborn-v0_8-darkgrid"),
                color_scheme=self.config.get("chart_color_scheme", "default"),
                save_to_file=self.config.get("chart_save_to_file", False),
                output_dir=self.config.get("chart_output_dir", "data/charts")
            )
            logger.info("图表生成功能已启用")
        elif self.config.get("chart_enabled", True) and not chart_available():
            logger.warning("图表生成已启用但 matplotlib 未安装")

        if self.ai_summarizer:
            self.daily_report_generator = DailyReportGenerator(
                openrouter_api_key=self.ai_summarizer.api_key,
                enable_ai=True,
                chart_config=chart_config
            )

    async def _start_scheduler(self):
        """Start the advanced scheduler for all monitoring tasks."""
        await asyncio.sleep(5)  # Wait for plugin to fully initialize

        if not self.config.get("enabled", False):
            return

        logger.info("启动高级调度器...")

        try:
            self.scheduler = SchedulerManager()
            await self.scheduler.start()

            # Add Bilibili monitoring task
            bili_cron = self.config.get("bilibili_cron", "")
            bili_interval = self.config.get("check_interval", 30)
            if bili_cron:
                bili_task = TaskConfig(
                    task_id="bilibili_monitor",
                    name="Bilibili UP Master Monitoring",
                    cron=bili_cron,
                    max_retries=3,
                    exponential_backoff=True
                )
            else:
                bili_task = TaskConfig(
                    task_id="bilibili_monitor",
                    name="Bilibili UP Master Monitoring",
                    interval_minutes=max(bili_interval, 5),
                    max_retries=3,
                    exponential_backoff=True
                )
            await self.scheduler.add_task(bili_task, self._check_all_up_masters)
            logger.info(f"已添加 Bilibili 监控任务 (cron={bili_cron or 'N/A'}, interval={bili_interval}分钟)")

            # Add Zhihu monitoring task if configured
            zhihu_feeds = self.config.get("zhihu_feeds", [])
            if zhihu_feeds:
                zhihu_cron = self.config.get("zhihu_cron", "")
                zhihu_interval = self.config.get("zhihu_check_interval", 60)
                if zhihu_cron:
                    zhihu_task = TaskConfig(
                        task_id="zhihu_monitor",
                        name="Zhihu RSS Monitoring",
                        cron=zhihu_cron,
                        max_retries=3,
                        exponential_backoff=True
                    )
                else:
                    zhihu_task = TaskConfig(
                        task_id="zhihu_monitor",
                        name="Zhihu RSS Monitoring",
                        interval_minutes=max(zhihu_interval, 30),
                        max_retries=3,
                        exponential_backoff=True
                    )
                await self.scheduler.add_task(zhihu_task, self._check_all_zhihu_feeds)
                logger.info(f"已添加 Zhihu 监控任务 (cron={zhihu_cron or 'N/A'}, interval={zhihu_interval}分钟)")

            # Add daily report task if enabled
            if self.config.get("daily_report_enabled", False):
                report_time = self.config.get("daily_report_time", "09:00")
                hour, minute = map(int, report_time.split(":"))
                daily_cron = f"{minute} {hour} * * *"
                daily_task = TaskConfig(
                    task_id="daily_report",
                    name="Daily Content Report",
                    cron=daily_cron,
                    max_retries=2,
                    exponential_backoff=False
                )
                await self.scheduler.add_task(daily_task, self._generate_daily_report)
                logger.info(f"已添加每日报告任务 (时间={report_time})")

            logger.info("高级调度器启动成功")

        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
            logger.info("回退到简单定时监控...")
            await self._start_monitoring()

    async def _start_monitoring(self):
        """Start the legacy monitoring timer task (fallback)."""
        await asyncio.sleep(5)  # Wait for plugin to fully initialize

        if not self.config.get("enabled", False):
            return

        logger.info("开始 B 站 UP 主监控任务 (简单定时模式)")
        self.is_running = True

        while self.is_running:
            try:
                await self._check_all_up_masters()
            except Exception as e:
                logger.error(f"监控任务执行出错: {e}")

            # Wait for next check
            interval_minutes = self.config.get("check_interval", 30)
            if interval_minutes < 5:
                interval_minutes = 5  # Minimum 5 minutes

            await asyncio.sleep(interval_minutes * 60)

    async def _check_all_up_masters(self):
        """Check all configured UP masters for new videos."""
        up_masters_config = self.config.get("up_masters", [])
        if not up_masters_config:
            logger.debug("未配置 UP 主列表，跳过检查")
            return

        # Parse UP master configs
        up_masters = []
        for up_config in up_masters_config:
            if isinstance(up_config, dict):
                up_masters.append(UPMasterConfig.from_dict(up_config))

        if not up_masters:
            return

        logger.info(f"开始检查 {len(up_masters)} 位 UP 主的更新")

        # Check for new videos
        max_videos = self.config.get("max_videos_per_check", 5)
        reports = await self.bili_monitor.check_multiple_up_masters(
            up_masters,
            max_videos=max_videos,
            fetch_descriptions=False,  # Don't fetch detailed descriptions to save API calls
            delay_between_checks=1.0
        )

        # Filter reports with new videos
        reports_with_videos = self.bili_monitor.get_reports_with_new_videos(reports)

        if not reports_with_videos:
            logger.info("没有发现新视频")
            return

        logger.info(f"发现 {len(reports_with_videos)} 位 UP 主有新视频")

        # Generate AI summaries if enabled
        if self.ai_summarizer and self.ai_summarizer.is_available():
            logger.info("正在生成 AI 总结...")
            await self.ai_summarizer.summarize_multiple_reports(reports_with_videos)

        # Send notifications
        await self._send_bilibili_reports(reports_with_videos)

        # Save to content history for search
        await self._save_bilibili_to_history(reports_with_videos)

    async def _check_all_zhihu_feeds(self):
        """Check all configured Zhihu RSS feeds for new items."""
        zhihu_feeds_config = self.config.get("zhihu_feeds", [])
        if not zhihu_feeds_config:
            logger.debug("未配置 Zhihu RSS 订阅列表，跳过检查")
            return

        # Parse feed configs
        feed_configs = []
        for feed_config in zhihu_feeds_config:
            if isinstance(feed_config, dict):
                feed_configs.append(ZhihuFeedConfig.from_dict(feed_config))

        # Filter enabled feeds
        enabled_feeds = [f for f in feed_configs if f.enabled]
        if not enabled_feeds:
            logger.debug("没有启用的 Zhihu RSS 订阅，跳过检查")
            return

        logger.info(f"开始检查 {len(enabled_feeds)} 个 Zhihu RSS 订阅")

        # Load state
        state = await self.zhihu_state_manager.load_state()

        # Check feeds
        reports = await self.zhihu_client.check_multiple_feeds(
            enabled_feeds,
            state,
            delay_between_checks=1.0
        )

        # Filter reports with new items
        reports_with_items = [r for r in reports if r.new_items]

        if not reports_with_items:
            logger.info("没有发现新内容")
            return

        logger.info(f"发现 {len(reports_with_items)} 个订阅有新内容")

        # Send notifications
        await self._send_zhihu_reports(reports_with_items)

        # Save to content history for search
        await self._save_zhihu_to_history(reports_with_items)

    async def _generate_daily_report(self, days: int = 1):
        """Generate and send daily content report.

        Args:
            days: Number of days to include in the report (default: 1)
        """
        if not self.daily_report_generator or not self.report_aggregator:
            logger.warning("每日报告生成器未初始化，跳过生成")
            return None

        logger.info(f"开始生成 {days} 天的内容报告...")

        try:
            # Collect content from last N days
            since = datetime.now() - timedelta(days=days)

            # Get Bilibili reports (from state)
            # Note: Current implementation doesn't store historical reports in state
            bili_reports: list[Any] = []  # Would need to store recent reports in state

            # Get Zhihu reports (from state)
            # Note: Current implementation doesn't store historical reports in state
            zhihu_reports: list[Any] = []  # Would need to store recent reports in state

            # Create report config
            report_config = DailyReportConfig(
                enabled=True,
                generation_time=self.config.get("daily_report_time", "09:00"),
                include_bilibili=True,
                include_zhihu=True,
                categorize_content=self.config.get("daily_report_categorize", True),
                generate_ai_summary=self.config.get("daily_report_ai_summary", True),
                highlight_important=True,
                max_items_per_category=self.config.get("daily_report_max_items", 10),
                min_importance_score=self.config.get("daily_report_min_importance", 0.3),
                output_format="markdown",
                include_statistics=True,
                include_trending=True
            )

            # Aggregate content
            report = self.report_aggregator.aggregate_all(
                bilibili_reports=bili_reports,
                zhihu_reports=zhihu_reports,
                since=since,
                min_importance=report_config.min_importance_score,
                max_items_per_category=report_config.max_items_per_category
            )

            # Generate report with charts
            chart_enabled = self.config.get("chart_enabled", True)
            markdown: str | None
            charts: dict[str, str | bytes]
            if chart_enabled and self.daily_report_generator.chart_generator:
                result = await self.daily_report_generator.generate(report, report_config, include_charts=True)
                if isinstance(result, tuple):
                    markdown, charts = result
                else:
                    markdown = result
                    charts = {}
            else:
                result = await self.daily_report_generator.generate(report, report_config, include_charts=False)
                if isinstance(result, tuple):
                    markdown, charts = result
                else:
                    markdown = result
                    charts = {}

            if markdown:
                # Send to configured targets
                await self._send_daily_report(markdown, charts)
                logger.info("每日报告生成并发送成功")
                return report
            else:
                logger.warning("每日报告生成失败或无内容")
                return None

        except Exception as e:
            logger.error(f"生成每日报告失败: {e}")
            return None

    async def _send_bilibili_reports(self, reports: list):
        """Send Bilibili monitor reports to configured targets."""
        target_groups = self.config.get("target_groups", [])
        if not target_groups:
            logger.warning("未配置消息发送目标，跳过发送")
            return

        # Format reports as Markdown
        if not self.bili_formatter:
            return

        send_summary_only = self.config.get("send_summary_only", False)
        batch_delay = self.config.get("batch_send_delay", 2)

        for target in target_groups:
            try:
                if send_summary_only:
                    # Send only AI summaries
                    for report in reports:
                        if report.ai_summary:
                            markdown = self.bili_formatter.format_summary_only(report)
                            if markdown:
                                chain = MessageChain().message(markdown)
                                await self.context.send_message(target, chain)
                                await asyncio.sleep(batch_delay)
                else:
                    # Send full report
                    markdown = self.bili_formatter.format_multiple_reports(reports)
                    if markdown:
                        chain = MessageChain().message(markdown)
                        await self.context.send_message(target, chain)

                logger.info(f"已发送 Bilibili 报告到 {target}")
            except Exception as e:
                logger.error(f"发送 Bilibili 报告到 {target} 失败: {e}")

    async def _send_zhihu_reports(self, reports: list):
        """Send Zhihu RSS reports to configured targets."""
        target_groups = self.config.get("target_groups", [])
        if not target_groups:
            logger.warning("未配置消息发送目标，跳过发送")
            return

        if not self.zhihu_formatter:
            return

        for target in target_groups:
            try:
                # Format and send reports
                markdown = self.zhihu_formatter.format_multiple_reports(reports)
                if markdown:
                    chain = MessageChain().message(markdown)
                    await self.context.send_message(target, chain)

                logger.info(f"已发送 Zhihu 报告到 {target}")
            except Exception as e:
                logger.error(f"发送 Zhihu 报告到 {target} 失败: {e}")

    async def _save_bilibili_to_history(self, reports: list):
        """Save Bilibili reports to content history for search."""
        try:
            from models.report import ContentItem, ContentSource, ContentCategory

            state = self.bili_state_manager.load_state()

            for report in reports:
                for video in report.new_videos:
                    # Create ContentItem
                    content_item = ContentItem(
                        title=video.title,
                        url=video.get_url(),
                        source=ContentSource.BILIBILI,
                        published=video.get_publish_datetime(),
                        author=report.up_master_name,
                        summary=video.desc[:500] if video.desc else None,
                        category=ContentCategory.OTHER,  # Could be improved with categorization
                        importance_score=0.5,  # Could be improved with scoring
                        source_data={
                            "bvid": video.bvid,
                            "aid": video.aid,
                            "up_mid": report.up_master_mid,
                            "play_count": video.play_count,
                            "like_count": video.like_count
                        }
                    )

                    # Add to history
                    state.add_content_to_history(content_item.to_dict())

            # Cleanup old history
            state.cleanup_old_history(max_items=1000)

            # Save state
            self.bili_state_manager.save_state()

            logger.debug(f"已保存 {sum(len(r.new_videos) for r in reports)} 条 Bilibili 内容到历史记录")

        except Exception as e:
            logger.error(f"保存 Bilibili 内容历史失败: {e}")

    async def _save_zhihu_to_history(self, reports: list):
        """Save Zhihu reports to content history for search."""
        try:
            from models.report import ContentItem, ContentSource, ContentCategory

            state = self.zhihu_state_manager.load_state()

            for report in reports:
                for item in report.new_items:
                    # Create ContentItem
                    content_item = ContentItem(
                        title=item.title,
                        url=item.link,
                        source=ContentSource.ZHIHU,
                        published=item.published,
                        author=item.author,
                        summary=item.description[:500] if item.description else None,
                        category=ContentCategory.OTHER,  # Could be improved with categorization
                        importance_score=0.5,  # Could be improved with scoring
                        source_data={
                            "guid": item.guid,
                            "feed_url": report.feed_url,
                            "feed_name": report.feed_name,
                            "bilibili_links": item.bilibili_links
                        }
                    )

                    # Add to history
                    state.add_content_to_history(content_item.to_dict())

            # Cleanup old history
            state.cleanup_old_history(max_items=1000)

            # Save state
            self.zhihu_state_manager.save_state()

            logger.debug(f"已保存 {sum(len(r.new_items) for r in reports)} 条 Zhihu 内容到历史记录")

        except Exception as e:
            logger.error(f"保存 Zhihu 内容历史失败: {e}")

    async def _send_daily_report(self, markdown: str, charts: dict[str, str | bytes] | None = None):
        """Send daily report to configured targets with optional charts."""
        target_groups = self.config.get("target_groups", [])
        if not target_groups:
            logger.warning("未配置消息发送目标，跳过发送")
            return

        for target in target_groups:
            try:
                # Create message chain with markdown
                chain = MessageChain().message(markdown)

                # Add charts if available
                if charts:
                    chart_output_format = self.config.get("chart_output_format", "png")

                    # If charts are base64 encoded, embed them in markdown
                    if chart_output_format == "base64":
                        chart_markdown = "\n\n## 📊 数据可视化\n\n"
                        for chart_name, chart_data in charts.items():
                            if isinstance(chart_data, str):  # base64
                                chart_markdown += f"![{chart_name}](data:image/png;base64,{chart_data})\n\n"
                        chain = MessageChain().message(markdown + chart_markdown)
                    else:
                        # For PNG/JPG, save temporarily and send as images
                        # Note: This requires AstrBot to support image sending
                        # For now, we'll just log that charts were generated
                        logger.info(f"生成了 {len(charts)} 个图表（格式: {chart_output_format}）")
                        # TODO: Implement image sending when AstrBot API supports it

                await self.context.send_message(target, chain)
                logger.info(f"已发送每日报告到 {target}")
            except Exception as e:
                logger.error(f"发送每日报告到 {target} 失败: {e}")

    @filter.command("bili_desc")
    async def bili_desc(self, event: AstrMessageEvent):
        """
        Get Bilibili video description and optionally extract/summarize links.

        Usage: /bili_desc <bvid|aid> [--extract] [--max N] [--depth basic|advanced] [--format markdown|text] [--summarize]
        """
        text = event.message_str.strip()
        parts = text.split()

        if len(parts) < 2:
            yield event.plain_result(
                "用法：/bili_desc <bvid|aid> [--extract] [--max N] [--depth basic|advanced] "
                "[--format markdown|text] [--summarize]"
            )
            return

        args = parts[1:]
        identifier = args[0]
        flags = parse_command_flags(args[1:])

        # Fetch video description
        try:
            desc = await get_bilibili_description(identifier)
        except Exception as e:
            yield event.plain_result(f"获取视频信息失败：{e}")
            return

        # Display basic info
        msg = [
            f"标题：{desc.title or '-'}",
            f"BV：{desc.bvid or '-'}，AV：{desc.aid or '-'}",
            "简介：",
            (desc.desc or "-"),
        ]
        yield event.plain_result("\n".join(msg))

        if not desc.desc:
            return

        # Handle URL extraction and summarization if requested
        if flags.get("extract"):
            result = await extract_and_summarize_urls(
                desc.desc,
                flags,
                tavily_api_key=self.config.get("tavily_api_key"),
                openrouter_api_key=self.config.get("openrouter_api_key")
            )

            if result.get("error"):
                yield event.plain_result(result["error"])
            elif result.get("message"):
                yield event.plain_result(result["message"])

    @filter.command("bili_latest")
    async def bili_latest(self, event: AstrMessageEvent):
        """
        Get latest video from a Bilibili user and optionally extract/summarize links.

        Usage: /bili_latest <mid> [--extract] [--max N] [--depth basic|advanced] [--format markdown|text] [--summarize]
        """
        text = event.message_str.strip()
        parts = text.split()

        if len(parts) < 2:
            yield event.plain_result(
                "用法：/bili_latest <mid> [--extract] [--max N] [--depth basic|advanced] "
                "[--format markdown|text] [--summarize]"
            )
            return

        args = parts[1:]
        mid = args[0]
        flags = parse_command_flags(args[1:])

        # Fetch latest video
        try:
            archives = await fetch_archives(mid, ps=5)
            latest = pick_latest_from_archives(archives)

            # Get identifier (prefer bvid)
            ident = latest.get("bvid") if isinstance(latest.get("bvid"), str) else None
            if not ident:
                aid_val = latest.get("aid")
                if isinstance(aid_val, (int, str)) and str(aid_val).isdigit():
                    ident = str(aid_val)
            if not ident:
                yield event.plain_result("该用户最新视频缺少 bvid/aid。")
                return

            desc = await get_bilibili_description(ident)
        except Exception as e:
            yield event.plain_result(f"获取最新视频失败：{e}")
            return

        # Display video info
        header = [
            "最新视频：",
            f"标题：{latest.get('title')}",
            f"BV：{latest.get('bvid')}，AV：{latest.get('aid')}",
            f"播放：{latest.get('play_count')}，发布时间：{latest.get('publish_time')}",
            "",
            "简介：",
            (desc.desc or "-"),
        ]
        yield event.plain_result("\n".join(map(str, header)))

        if not desc.desc:
            return

        # Handle URL extraction and summarization if requested
        if flags.get("extract"):
            result = await extract_and_summarize_urls(
                desc.desc,
                flags,
                tavily_api_key=self.config.get("tavily_api_key"),
                openrouter_api_key=self.config.get("openrouter_api_key")
            )

            if result.get("error"):
                yield event.plain_result(result["error"])
            elif result.get("message"):
                yield event.plain_result(result["message"])

    @filter.command("bili_monitor")
    async def bili_monitor_cmd(self, event: AstrMessageEvent):
        """
        Manually trigger monitoring check for configured UP masters.

        Usage: /bili_monitor
        """
        if not self.config.get("enabled", False):
            yield event.plain_result("B 站监控功能未启用，请在配置中启用后重试。")
            return

        up_masters_config = self.config.get("up_masters", [])
        if not up_masters_config:
            yield event.plain_result("未配置 UP 主列表，请先在配置中添加要监控的 UP 主。")
            return

        yield event.plain_result("开始检查 UP 主更新...")

        try:
            # Parse UP master configs
            up_masters = []
            for up_config in up_masters_config:
                if isinstance(up_config, dict):
                    up_masters.append(UPMasterConfig.from_dict(up_config))

            # Check for new videos
            max_videos = self.config.get("max_videos_per_check", 5)
            reports = await self.bili_monitor.check_multiple_up_masters(
                up_masters,
                max_videos=max_videos,
                fetch_descriptions=False,
                delay_between_checks=1.0
            )

            # Filter reports with new videos
            reports_with_videos = self.bili_monitor.get_reports_with_new_videos(reports)

            if not reports_with_videos:
                yield event.plain_result("没有发现新视频。")
                return

            yield event.plain_result(f"发现 {len(reports_with_videos)} 位 UP 主有新视频，正在生成报告...")

            # Generate AI summaries if enabled
            if self.ai_summarizer and self.ai_summarizer.is_available():
                await self.ai_summarizer.summarize_multiple_reports(reports_with_videos)

            # Format and send report
            if self.bili_formatter:
                markdown = self.bili_formatter.format_multiple_reports(reports_with_videos)
                if markdown:
                    yield event.plain_result(markdown)

        except Exception as e:
            logger.error(f"手动检查失败: {e}")
            yield event.plain_result(f"检查失败：{e}")

    @filter.command("zhihu_check")
    async def zhihu_check_cmd(self, event: AstrMessageEvent):
        """
        Manually trigger Zhihu RSS feed check.

        Usage: /zhihu_check
        """
        zhihu_feeds_config = self.config.get("zhihu_feeds", [])
        if not zhihu_feeds_config:
            yield event.plain_result("未配置知乎 RSS 订阅源，请先在配置中添加订阅源。")
            return

        yield event.plain_result("开始检查知乎 RSS 订阅源...")

        try:
            # Parse feed configs
            feeds = []
            for feed_config in zhihu_feeds_config:
                if isinstance(feed_config, dict) and feed_config.get("enabled", True):
                    feeds.append(ZhihuFeedConfig.from_dict(feed_config))

            if not feeds:
                yield event.plain_result("没有启用的订阅源。")
                return

            # Load state
            state = self.zhihu_state_manager.load_state()

            # Check feeds
            reports = await self.zhihu_client.check_multiple_feeds(
                feeds,
                state,
                delay_between_checks=1.0
            )

            # Save state
            self.zhihu_state_manager.save_state()

            # Filter reports with new items
            reports_with_items = [r for r in reports if r.new_items]

            if not reports_with_items:
                yield event.plain_result("没有发现新内容。")
                return

            yield event.plain_result(f"发现 {len(reports_with_items)} 个订阅源有新内容，正在生成报告...")

            # Format and send report
            if self.zhihu_formatter:
                markdown = self.zhihu_formatter.format_multiple_reports(reports_with_items)
                if markdown:
                    yield event.plain_result(markdown)

        except Exception as e:
            logger.error(f"知乎检查失败: {e}")
            yield event.plain_result(f"检查失败：{e}")

    @filter.command("daily_report")
    async def daily_report_cmd(self, event: AstrMessageEvent):
        """
        Manually generate and view daily content report.

        Usage: /daily_report [--days N]

        Flags:
        --days N: Generate report for last N days (default: 1)
        """
        if not self.daily_report_generator or not self.report_aggregator:
            yield event.plain_result("每日报告功能未启用。请确保已配置 AI 总结功能（需要 OpenRouter API Key）。")
            return

        yield event.plain_result("开始生成每日内容报告...")

        try:
            # Parse command flags
            text = event.message_str.strip()
            parts = text.split()

            # Parse --days flag
            days = 1
            if "--days" in parts:
                try:
                    days_idx = parts.index("--days")
                    if days_idx + 1 < len(parts):
                        days = int(parts[days_idx + 1])
                        days = max(1, min(days, 7))  # Limit to 1-7 days
                except (ValueError, IndexError):
                    yield event.plain_result("⚠️ --days 参数格式错误，使用默认值 1 天")
                    days = 1

            # Collect content from last N days
            since = datetime.now() - timedelta(days=days)

            # Load Bilibili state and get recent reports
            # Note: Current implementation doesn't store historical reports in state
            # For now, we'll create an empty list - this is a known limitation
            bili_reports: list[Any] = []

            # Load Zhihu state and get recent reports
            # Note: Current implementation doesn't store historical reports in state
            # For now, we'll create an empty list - this is a known limitation
            zhihu_reports: list[Any] = []

            # Create report config from plugin config
            report_config = DailyReportConfig(
                enabled=True,
                generation_time=self.config.get("daily_report_time", "09:00"),
                include_bilibili=self.config.get("daily_report_include_bilibili", True),
                include_zhihu=self.config.get("daily_report_include_zhihu", True),
                categorize_content=self.config.get("daily_report_categorize", True),
                generate_ai_summary=self.config.get("daily_report_ai_summary", True),
                highlight_important=True,
                max_items_per_category=self.config.get("daily_report_max_items", 10),
                min_importance_score=self.config.get("daily_report_min_importance", 0.3),
                output_format="markdown",
                include_statistics=True,
                include_trending=True
            )

            # Aggregate content
            report = self.report_aggregator.aggregate_all(
                bilibili_reports=bili_reports,
                zhihu_reports=zhihu_reports,
                since=since,
                min_importance=report_config.min_importance_score,
                max_items_per_category=report_config.max_items_per_category
            )

            # Check if we have any content
            if report.total_items == 0:
                yield event.plain_result(
                    f"📊 过去 {days} 天没有收集到内容。\n\n"
                    "💡 提示：每日报告需要从监控任务中收集内容。当前实现的限制是不存储历史报告数据。\n"
                    "建议：启用自动监控功能，让插件持续收集内容后再查看每日报告。"
                )
                return

            # Generate report with charts if enabled
            chart_enabled = self.config.get("chart_enabled", True)
            markdown: str | None
            charts: dict[str, str | bytes]
            if chart_enabled and self.daily_report_generator.chart_generator:
                yield event.plain_result(f"正在生成报告和图表（共 {report.total_items} 条内容）...")
                result = await self.daily_report_generator.generate(
                    report,
                    report_config,
                    include_charts=True
                )

                if isinstance(result, tuple):
                    markdown, charts = result

                    # Send markdown report
                    if markdown:
                        yield event.plain_result(markdown)

                    # Send charts (if any)
                    if charts:
                        yield event.plain_result(f"\n📊 生成了 {len(charts)} 个图表")
                        # Note: Sending chart images would require image message support
                        # For now, we just notify that charts were generated
                        if self.config.get("chart_save_to_file", False):
                            chart_dir = self.config.get("chart_output_dir", "data/charts")
                            yield event.plain_result(f"图表已保存到: {chart_dir}/")
                else:
                    # result is str in this case
                    if isinstance(result, str):
                        markdown = result
                        if markdown:
                            yield event.plain_result(markdown)
            else:
                yield event.plain_result(f"正在生成报告（共 {report.total_items} 条内容）...")
                result = await self.daily_report_generator.generate(
                    report,
                    report_config,
                    include_charts=False
                )
                if isinstance(result, tuple):
                    markdown, _ = result
                else:
                    markdown = result
                if markdown:
                    yield event.plain_result(markdown)

            logger.info(f"手动生成每日报告成功 (days={days}, items={report.total_items})")

        except Exception as e:
            logger.error(f"生成每日报告失败: {e}", exc_info=True)
            yield event.plain_result(f"生成报告失败：{e}")

    async def terminate(self):
        """Clean up plugin resources on shutdown."""
        logger.info("正在停止内容监控与分析插件...")
        self.is_running = False

        # Stop scheduler if running
        if self.scheduler:
            try:
                await self.scheduler.stop()
                logger.info("调度器已停止")
            except Exception as e:
                logger.error(f"停止调度器失败: {e}")

        # Stop legacy monitor task if running
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("内容监控与分析插件已停止")

    @filter.command("search")
    async def handle_search(self, event: AstrMessageEvent):
        """
        Search through monitored content.

        Usage:
            /search <keywords> [--category <category>] [--source <source>] [--days <N>] [--limit <N>]

        Examples:
            /search Python 机器学习
            /search 编程 --category technology
            /search --source bilibili --days 7
            /search AI --limit 10
        """
        # Parse command
        message_str = event.message_str
        parts = message_str.split(maxsplit=1)

        if len(parts) < 2:
            yield event.plain_result(
                "📖 搜索命令使用说明\n\n"
                "用法: /search <关键词> [选项]\n\n"
                "选项:\n"
                "  --category <类别>  按类别筛选 (technology/entertainment/education/news/lifestyle/other)\n"
                "  --source <来源>    按来源筛选 (bilibili/zhihu)\n"
                "  --days <天数>      搜索最近N天的内容 (默认: 30)\n"
                "  --limit <数量>     限制结果数量 (默认: 20)\n"
                "  --sort <排序>      排序方式 (relevance/date/importance, 默认: relevance)\n\n"
                "示例:\n"
                "  /search Python 机器学习\n"
                "  /search 编程 --category technology\n"
                "  /search --source bilibili --days 7\n"
                "  /search AI --limit 10 --sort importance"
            )
            return

        # Parse arguments
        args_str = parts[1]
        flags = parse_command_flags(args_str)

        # Extract keywords (everything that's not a flag)
        keywords = []
        words = args_str.split()
        i = 0
        while i < len(words):
            if words[i].startswith("--"):
                # Skip flag and its value
                i += 2
            else:
                keywords.append(words[i])
                i += 1

        # Build search query
        from models.report import ContentCategory, ContentSource

        query = SearchQuery(
            keywords=keywords,
            limit=int(flags.get("limit", 20)),
            sort_by=flags.get("sort", "relevance")
        )

        # Parse category filter
        if "category" in flags:
            try:
                category = ContentCategory(flags["category"].lower())
                query.categories = [category]
            except ValueError:
                yield event.plain_result(
                    f"❌ 无效的类别: {flags['category']}\n\n"
                    "有效类别: technology, entertainment, education, news, lifestyle, other"
                )
                return

        # Parse source filter
        if "source" in flags:
            try:
                source = ContentSource(flags["source"].lower())
                query.sources = [source]
            except ValueError:
                yield event.plain_result(
                    f"❌ 无效的来源: {flags['source']}\n\n"
                    "有效来源: bilibili, zhihu"
                )
                return

        # Parse date range
        if "days" in flags:
            try:
                days = int(flags["days"])
                query.end_date = datetime.now()
                query.start_date = query.end_date - timedelta(days=days)
            except ValueError:
                yield event.plain_result(f"❌ 无效的天数: {flags['days']}")
                return

        # Load content history into search engine
        try:
            # Load from Bilibili state
            bili_state = self.bili_state_manager.load_state()
            if bili_state.content_history:
                from models.report import ContentItem
                bili_items = [ContentItem.from_dict(item) for item in bili_state.content_history]
                self.search_engine.index_content(bili_items)

            # Load from Zhihu state
            zhihu_state = self.zhihu_state_manager.load_state()
            if zhihu_state.content_history:
                from models.report import ContentItem
                zhihu_items = [ContentItem.from_dict(item) for item in zhihu_state.content_history]
                self.search_engine.index_content(zhihu_items)

            # Perform search
            results = self.search_engine.search(query)

            # Format results
            if not results:
                yield event.plain_result(
                    f"🔍 未找到匹配的内容\n\n"
                    f"搜索关键词: {' '.join(keywords)}\n"
                    f"提示: 尝试使用不同的关键词或调整筛选条件"
                )
                return

            # Build result message
            lines = [
                "# 🔍 搜索结果",
                "",
                f"**关键词**: {' '.join(keywords)}",
                f"**结果数**: {len(results)}",
                ""
            ]

            # Add filter info
            if query.categories:
                lines.append(f"**类别筛选**: {', '.join(c.value for c in query.categories)}")
            if query.sources:
                lines.append(f"**来源筛选**: {', '.join(s.value for s in query.sources)}")
            if query.start_date and query.end_date:
                lines.append(f"**时间范围**: {query.start_date.strftime('%Y-%m-%d')} 至 {query.end_date.strftime('%Y-%m-%d')}")

            lines.append("")
            lines.append("---")
            lines.append("")

            # Add results
            for idx, result in enumerate(results, 1):
                item = result.item
                lines.append(f"## {idx}. {item.title}")

                if item.author:
                    lines.append(f"👤 **作者**: {item.author}")

                lines.append(f"📂 **类别**: {item.category.value}")
                lines.append(f"📍 **来源**: {item.source.value}")

                if item.published:
                    lines.append(f"📅 **发布**: {item.published.strftime('%Y-%m-%d %H:%M')}")

                lines.append(f"⭐ **重要度**: {item.importance_score:.2f}")

                if result.relevance_score > 0:
                    lines.append(f"🎯 **相关度**: {result.relevance_score:.2f}")

                if result.matched_fields:
                    lines.append(f"✅ **匹配字段**: {', '.join(result.matched_fields)}")

                lines.append(f"🔗 **链接**: {item.url}")

                if item.summary:
                    # Truncate summary if too long
                    summary = item.summary[:200] + "..." if len(item.summary) > 200 else item.summary
                    lines.append(f"\n{summary}")

                lines.append("")

            # Add statistics
            stats = self.search_engine.get_statistics()
            lines.append("---")
            lines.append("")
            lines.append("## 📊 索引统计")
            lines.append(f"- 总内容数: {stats['total_items']}")
            if stats['by_source']:
                lines.append(f"- 按来源: {', '.join(f'{k}({v})' for k, v in stats['by_source'].items())}")
            if stats['by_category']:
                lines.append(f"- 按类别: {', '.join(f'{k}({v})' for k, v in stats['by_category'].items())}")

            yield event.plain_result("\n".join(lines))

        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 搜索失败: {str(e)}")

    @filter.command("filter")
    async def handle_filter(self, event: AstrMessageEvent):
        """
        Filter monitored content by various criteria.

        Usage:
            /filter [--category <category>] [--source <source>] [--min-importance <score>] [--days <N>] [--limit <N>]

        Examples:
            /filter --category technology
            /filter --source bilibili --min-importance 0.7
            /filter --days 7 --limit 15
        """
        # Parse command
        message_str = event.message_str
        parts = message_str.split(maxsplit=1)

        # Parse flags
        flags = {}
        if len(parts) > 1:
            flags = parse_command_flags(parts[1])

        # Build search query
        from models.report import ContentCategory, ContentSource

        query = SearchQuery(
            keywords=[],  # No keyword search, just filtering
            limit=int(flags.get("limit", 20)),
            sort_by=flags.get("sort", "date"),
            sort_order="desc"
        )

        # Parse category filter
        if "category" in flags:
            try:
                category = ContentCategory(flags["category"].lower())
                query.categories = [category]
            except ValueError:
                yield event.plain_result(
                    f"❌ 无效的类别: {flags['category']}\n\n"
                    "有效类别: technology, entertainment, education, news, lifestyle, other"
                )
                return

        # Parse source filter
        if "source" in flags:
            try:
                source = ContentSource(flags["source"].lower())
                query.sources = [source]
            except ValueError:
                yield event.plain_result(
                    f"❌ 无效的来源: {flags['source']}\n\n"
                    "有效来源: bilibili, zhihu"
                )
                return

        # Parse importance filter
        if "min-importance" in flags or "min_importance" in flags:
            try:
                min_imp = float(flags.get("min-importance", flags.get("min_importance", 0)))
                query.min_importance = min_imp
            except ValueError:
                yield event.plain_result(f"❌ 无效的重要度: {flags.get('min-importance', flags.get('min_importance'))}")
                return

        if "max-importance" in flags or "max_importance" in flags:
            try:
                max_imp = float(flags.get("max-importance", flags.get("max_importance", 1.0)))
                query.max_importance = max_imp
            except ValueError:
                yield event.plain_result(f"❌ 无效的重要度: {flags.get('max-importance', flags.get('max_importance'))}")
                return

        # Parse date range
        if "days" in flags:
            try:
                days = int(flags["days"])
                query.end_date = datetime.now()
                query.start_date = query.end_date - timedelta(days=days)
            except ValueError:
                yield event.plain_result(f"❌ 无效的天数: {flags['days']}")
                return

        # Load content history into search engine
        try:
            # Clear previous index
            self.search_engine.clear_index()

            # Load from Bilibili state
            bili_state = self.bili_state_manager.load_state()
            if bili_state.content_history:
                from models.report import ContentItem
                bili_items = [ContentItem.from_dict(item) for item in bili_state.content_history]
                self.search_engine.index_content(bili_items)

            # Load from Zhihu state
            zhihu_state = self.zhihu_state_manager.load_state()
            if zhihu_state.content_history:
                from models.report import ContentItem
                zhihu_items = [ContentItem.from_dict(item) for item in zhihu_state.content_history]
                self.search_engine.index_content(zhihu_items)

            # Perform search (filtering only)
            results = self.search_engine.search(query)

            # Format results
            if not results:
                filter_desc = []
                if query.categories:
                    filter_desc.append(f"类别={', '.join(c.value for c in query.categories)}")
                if query.sources:
                    filter_desc.append(f"来源={', '.join(s.value for s in query.sources)}")
                if query.min_importance:
                    filter_desc.append(f"最低重要度={query.min_importance}")
                if query.start_date and query.end_date:
                    filter_desc.append(f"时间范围={query.start_date.strftime('%Y-%m-%d')} 至 {query.end_date.strftime('%Y-%m-%d')}")

                yield event.plain_result(
                    f"🔍 未找到匹配的内容\n\n"
                    f"筛选条件: {', '.join(filter_desc) if filter_desc else '无'}\n"
                    f"提示: 尝试调整筛选条件"
                )
                return

            # Build result message
            lines = [
                "# 🔍 筛选结果",
                "",
                f"**结果数**: {len(results)}",
                ""
            ]

            # Add filter info
            if query.categories:
                lines.append(f"**类别**: {', '.join(c.value for c in query.categories)}")
            if query.sources:
                lines.append(f"**来源**: {', '.join(s.value for s in query.sources)}")
            if query.min_importance:
                lines.append(f"**最低重要度**: {query.min_importance}")
            if query.max_importance and query.max_importance < 1.0:
                lines.append(f"**最高重要度**: {query.max_importance}")
            if query.start_date and query.end_date:
                lines.append(f"**时间范围**: {query.start_date.strftime('%Y-%m-%d')} 至 {query.end_date.strftime('%Y-%m-%d')}")

            lines.append("")
            lines.append("---")
            lines.append("")

            # Add results
            for idx, result in enumerate(results, 1):
                item = result.item
                lines.append(f"## {idx}. {item.title}")

                if item.author:
                    lines.append(f"👤 **作者**: {item.author}")

                lines.append(f"📂 **类别**: {item.category.value}")
                lines.append(f"📍 **来源**: {item.source.value}")

                if item.published:
                    lines.append(f"📅 **发布**: {item.published.strftime('%Y-%m-%d %H:%M')}")

                lines.append(f"⭐ **重要度**: {item.importance_score:.2f}")
                lines.append(f"🔗 **链接**: {item.url}")

                if item.summary:
                    # Truncate summary if too long
                    summary = item.summary[:200] + "..." if len(item.summary) > 200 else item.summary
                    lines.append(f"\n{summary}")

                lines.append("")

            # Add statistics
            stats = self.search_engine.get_statistics()
            lines.append("---")
            lines.append("")
            lines.append("## 📊 索引统计")
            lines.append(f"- 总内容数: {stats['total_items']}")
            if stats['by_source']:
                lines.append(f"- 按来源: {', '.join(f'{k}({v})' for k, v in stats['by_source'].items())}")
            if stats['by_category']:
                lines.append(f"- 按类别: {', '.join(f'{k}({v})' for k, v in stats['by_category'].items())}")

            yield event.plain_result("\n".join(lines))

        except Exception as e:
            logger.error(f"筛选失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 筛选失败: {str(e)}")

    @filter.command("export")
    async def handle_export(self, event: AstrMessageEvent):
        """
        Export daily report in various formats.

        Usage:
            /export [--days N] [--format json|markdown|html] [--charts] [--output filename]

        Flags:
            --days N: Generate report for last N days (default: 1)
            --format: Export format (json/markdown/html, default: json)
            --charts: Include charts in export
            --output: Custom output filename

        Examples:
            /export
            /export --format markdown
            /export --days 7 --format html --charts
            /export --format json --output my_report.json
        """
        try:
            # Parse command flags
            flags = parse_command_flags(event.message_str)

            # Get parameters
            days = int(flags.get("days", 1))
            export_format = flags.get("format", "json").lower()
            include_charts = "charts" in flags
            custom_filename = flags.get("output")

            # Validate format
            if export_format not in ["json", "markdown", "html"]:
                yield event.plain_result("❌ 不支持的格式。支持的格式: json, markdown, html")
                return

            # Validate days
            if days < 1 or days > 30:
                yield event.plain_result("❌ 天数必须在 1-30 之间")
                return

            yield event.plain_result(f"📤 正在生成 {days} 天的报告并导出为 {export_format.upper()} 格式...")

            # Generate report
            report = await self._generate_daily_report(days)

            if not report:
                yield event.plain_result("❌ 生成报告失败，请检查是否有监控数据")
                return

            # Generate charts if requested
            charts: dict[str, str | bytes] | None = None
            if include_charts and chart_available():
                try:
                    from utils.chart_generator import ChartGenerator

                    chart_gen = ChartGenerator()
                    charts = {}

                    # Generate category distribution chart (bar chart)
                    chart_result = await chart_gen.generate_category_distribution_bar(report)
                    if chart_result:
                        charts["category_distribution"] = chart_result

                    # Generate importance distribution chart
                    chart_result = await chart_gen.generate_importance_distribution(report)
                    if chart_result:
                        charts["importance_distribution"] = chart_result

                except Exception as e:
                    logger.warning(f"生成图表失败: {e}")
                    charts = {}

            # Export report
            result = self.report_exporter.export_report(
                report=report,
                format=export_format,
                filename=custom_filename,
                charts=charts
            )

            if result.success:
                lines = [
                    "✅ 报告导出成功！",
                    "",
                    f"📁 文件路径: {result.file_path}",
                    f"📊 格式: {result.format.upper() if result.format else 'UNKNOWN'}",
                    f"💾 文件大小: {result.size_bytes:,} 字节 ({result.size_bytes / 1024:.2f} KB)",
                    "",
                    "📋 报告内容:",
                    f"- 总内容数: {report.total_items}",
                    f"- B站视频: {report.bilibili_items}",
                    f"- 知乎内容: {report.zhihu_items}",
                    f"- 分类数: {len(report.sections)}"
                ]

                if charts:
                    lines.extend([
                        "",
                        f"📊 包含图表: {len(charts)} 个"
                    ])

                yield event.plain_result("\n".join(lines))
            else:
                yield event.plain_result(f"❌ 导出失败: {result.error}")

        except ValueError as e:
            yield event.plain_result(f"❌ 参数错误: {str(e)}")
        except Exception as e:
            logger.error(f"导出失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 导出失败: {str(e)}")

    @filter.command("archive")
    async def handle_archive(self, event: AstrMessageEvent):
        """
        Manage report archives.

        Usage:
            /archive [action] [options]

        Actions:
            list: List archived reports (default)
            save: Archive current daily report
            view <id>: View archived report details
            delete <id>: Delete an archived report
            cleanup: Delete old archives (90+ days)
            stats: Show archive statistics

        Flags (for list):
            --days N: List archives from last N days
            --limit N: Limit number of results

        Examples:
            /archive
            /archive list --days 30
            /archive save
            /archive view 20250101
            /archive delete 20250101
            /archive cleanup
            /archive stats
        """
        try:
            # Parse command
            parts = event.message_str.split(maxsplit=1)
            action = "list"
            args = ""

            if len(parts) > 1:
                rest = parts[1].strip()
                if rest:
                    action_parts = rest.split(maxsplit=1)
                    action = action_parts[0].lower()
                    args = action_parts[1] if len(action_parts) > 1 else ""

            # Handle different actions
            if action == "list":
                await self._handle_archive_list(event, args)
            elif action == "save":
                await self._handle_archive_save(event, args)
            elif action == "view":
                await self._handle_archive_view(event, args)
            elif action == "delete":
                await self._handle_archive_delete(event, args)
            elif action == "cleanup":
                await self._handle_archive_cleanup(event, args)
            elif action == "stats":
                await self._handle_archive_stats(event, args)
            else:
                yield event.plain_result(
                    f"❌ 未知操作: {action}\n"
                    "支持的操作: list, save, view, delete, cleanup, stats"
                )

        except Exception as e:
            logger.error(f"归档操作失败: {e}", exc_info=True)
            yield event.plain_result(f"❌ 归档操作失败: {str(e)}")

    async def _handle_archive_list(self, event: AstrMessageEvent, args: str):
        """Handle archive list command."""
        flags = parse_command_flags(args.split())

        days = int(flags.get("days", 0)) if "days" in flags else None
        limit = int(flags.get("limit", 20))

        # Get date range
        start_date = None
        if days:
            start_date = datetime.now() - timedelta(days=days)

        # List archives
        archives = self.archive_manager.list_archives(
            start_date=start_date,
            limit=limit
        )

        if not archives:
            yield event.plain_result("📦 暂无归档报告")
            return

        lines = [
            f"📦 归档报告列表 (共 {len(archives)} 个)",
            ""
        ]

        for idx, archive in enumerate(archives, 1):
            lines.extend([
                f"{idx}. **{archive.archive_id}**",
                f"   📅 报告日期: {archive.report_date.strftime('%Y-%m-%d')}",
                f"   🕐 归档时间: {archive.archived_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"   📊 内容数: {archive.total_items} (B站: {archive.bilibili_items}, 知乎: {archive.zhihu_items})",
                f"   💾 文件大小: {archive.file_size:,} 字节 ({archive.file_size / 1024:.2f} KB)",
                ""
            ])

        yield event.plain_result("\n".join(lines))

    async def _handle_archive_save(self, event: AstrMessageEvent, args: str):
        """Handle archive save command."""
        flags = parse_command_flags(args.split())
        days = int(flags.get("days", 1))

        yield event.plain_result(f"📦 正在生成并归档 {days} 天的报告...")

        # Generate report
        report = await self._generate_daily_report(days)

        if not report:
            yield event.plain_result("❌ 生成报告失败，请检查是否有监控数据")
            return

        # Archive report
        metadata = self.archive_manager.archive_report(report)

        if metadata:
            lines = [
                "✅ 报告归档成功！",
                "",
                f"📦 归档ID: {metadata.archive_id}",
                f"📅 报告日期: {metadata.report_date.strftime('%Y-%m-%d')}",
                f"📊 内容数: {metadata.total_items}",
                f"💾 文件大小: {metadata.file_size:,} 字节 ({metadata.file_size / 1024:.2f} KB)",
                f"📁 文件路径: {metadata.file_path}"
            ]
            yield event.plain_result("\n".join(lines))
        else:
            yield event.plain_result("❌ 归档失败")

    async def _handle_archive_view(self, event: AstrMessageEvent, args: str):
        """Handle archive view command."""
        archive_id = args.strip()

        if not archive_id:
            yield event.plain_result("❌ 请指定归档ID，例如: /archive view 20250101")
            return

        # Load report
        report = self.archive_manager.load_report(archive_id)

        if not report:
            yield event.plain_result(f"❌ 未找到归档: {archive_id}")
            return

        # Display report summary
        lines = [
            f"📦 归档报告: {archive_id}",
            "",
            f"📋 {report.title}",
            f"📅 报告日期: {report.report_date.strftime('%Y年%m月%d日')}",
            "",
            "## 📊 统计信息",
            f"- 总内容数: {report.total_items}",
            f"- B站视频: {report.bilibili_items}",
            f"- 知乎内容: {report.zhihu_items}",
            f"- 分类数: {len(report.sections)}",
            ""
        ]

        if report.executive_summary:
            lines.extend([
                "## 📋 执行摘要",
                report.executive_summary,
                ""
            ])

        if report.trending_topics:
            topics_str = " · ".join(report.trending_topics)
            lines.extend([
                "## 🔥 热门话题",
                topics_str,
                ""
            ])

        # Show sections summary
        lines.append("## 📂 内容分类")
        for section in report.sections:
            lines.append(f"- {section.category.value}: {len(section.items)} 项")

        yield event.plain_result("\n".join(lines))

    async def _handle_archive_delete(self, event: AstrMessageEvent, args: str):
        """Handle archive delete command."""
        archive_id = args.strip()

        if not archive_id:
            yield event.plain_result("❌ 请指定归档ID，例如: /archive delete 20250101")
            return

        # Delete archive
        success = self.archive_manager.delete_archive(archive_id)

        if success:
            yield event.plain_result(f"✅ 已删除归档: {archive_id}")
        else:
            yield event.plain_result(f"❌ 删除失败: {archive_id}")

    async def _handle_archive_cleanup(self, event: AstrMessageEvent, args: str):
        """Handle archive cleanup command."""
        flags = parse_command_flags(args.split())
        days = int(flags.get("days", 90))

        yield event.plain_result(f"🧹 正在清理 {days} 天前的归档...")

        deleted_count = self.archive_manager.cleanup_old_archives(days)

        if deleted_count > 0:
            yield event.plain_result(f"✅ 已清理 {deleted_count} 个旧归档")
        else:
            yield event.plain_result("✅ 没有需要清理的归档")

    async def _handle_archive_stats(self, event: AstrMessageEvent, args: str):
        """Handle archive stats command."""
        stats = self.archive_manager.get_statistics()

        if stats["total_archives"] == 0:
            yield event.plain_result("📦 暂无归档报告")
            return

        lines = [
            "📊 归档统计信息",
            "",
            f"📦 总归档数: {stats['total_archives']}",
            f"💾 总大小: {stats['total_size_mb']} MB ({stats['total_size_bytes']:,} 字节)",
            f"📝 总内容数: {stats['total_items']}",
            ""
        ]

        if stats["date_range"]:
            lines.extend([
                "📅 日期范围:",
                f"- 最早: {stats['date_range']['earliest']}",
                f"- 最新: {stats['date_range']['latest']}"
            ])

        yield event.plain_result("\n".join(lines))
