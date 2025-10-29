"""
AstrBot SAST Plugin - Content Monitoring & Analysis

Provides comprehensive content monitoring and analysis tools including:
- Bilibili video tools (description fetching, link extraction, AI summarization)
- UP master monitoring with new video detection
- Zhihu RSS feed monitoring with Bilibili link extraction
- Advanced scheduling with cron support
- AI-powered daily reports with content aggregation
"""
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

import os
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

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

# Utilities
from utils.command_utils import (
    parse_command_flags,
    extract_and_summarize_urls,
)
from utils.chart_generator import ChartConfig, chart_available


@register("astrbot-sast", "AstroAir", "内容监控与分析工具集 (Bilibili/Zhihu/AI报告)", "2.0.0")
class SASTPlugin(Star):
    """
    AstrBot SAST Plugin - Content Monitoring & Analysis

    Provides comprehensive content monitoring and analysis:
    - /bili_desc: Get video description and optionally extract/summarize links
    - /bili_latest: Get latest video from a user and optionally extract/summarize links
    - /bili_monitor: Manually trigger monitoring check for configured UP masters
    - /zhihu_check: Manually trigger Zhihu RSS feed check (planned)
    - /daily_report: Manually generate daily content report (planned)

    Background tasks:
    - Bilibili UP master monitoring
    - Zhihu RSS feed monitoring
    - Daily report generation
    """

    def __init__(self, context: Context):
        super().__init__(context)

        # Get configuration from context
        self.config = {}
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

    async def _generate_daily_report(self):
        """Generate and send daily content report."""
        if not self.daily_report_generator or not self.report_aggregator:
            logger.warning("每日报告生成器未初始化，跳过生成")
            return

        logger.info("开始生成每日内容报告...")

        try:
            # Collect content from last 24 hours
            since = datetime.now() - timedelta(days=1)

            # Get Bilibili reports (from state)
            bili_state = await self.bili_state_manager.load_state()
            bili_reports = []  # Would need to store recent reports in state

            # Get Zhihu reports (from state)
            zhihu_state = await self.zhihu_state_manager.load_state()
            zhihu_reports = []  # Would need to store recent reports in state

            # Create report config
            report_config = DailyReportConfig(
                categorize=self.config.get("daily_report_categorize", True),
                ai_summary=self.config.get("daily_report_ai_summary", True),
                min_importance=self.config.get("daily_report_min_importance", 0.3),
                max_items_per_category=self.config.get("daily_report_max_items", 10),
                output_format="markdown"
            )

            # Aggregate content
            report = self.report_aggregator.aggregate_all(
                bilibili_reports=bili_reports,
                zhihu_reports=zhihu_reports,
                since=since,
                min_importance=report_config.min_importance,
                max_items_per_category=report_config.max_items_per_category
            )

            # Generate report with charts
            chart_enabled = self.config.get("chart_enabled", True)
            if chart_enabled and self.daily_report_generator.chart_generator:
                result = await self.daily_report_generator.generate(report, report_config, include_charts=True)
                if isinstance(result, tuple):
                    markdown, charts = result
                else:
                    markdown = result
                    charts = {}
            else:
                markdown = await self.daily_report_generator.generate(report, report_config, include_charts=False)
                charts = {}

            if markdown:
                # Send to configured targets
                await self._send_daily_report(markdown, charts)
                logger.info("每日报告生成并发送成功")
            else:
                logger.warning("每日报告生成失败或无内容")

        except Exception as e:
            logger.error(f"生成每日报告失败: {e}")

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

        batch_delay = self.config.get("batch_send_delay", 2)

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
