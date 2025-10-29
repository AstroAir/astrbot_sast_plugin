"""
Content aggregation service for daily reports.

Collects content from multiple sources (Bilibili, Zhihu) and prepares it
for AI-powered daily report generation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from models.report import ContentItem, ContentSource, ContentCategory, DailyReport
from models.bilibili import MonitorReport as BilibiliMonitorReport
from models.zhihu import ZhihuMonitorReport


logger = logging.getLogger(__name__)


class ReportAggregator:
    """Aggregates content from multiple sources for daily reports."""
    
    def __init__(self):
        """Initialize report aggregator."""
        self.category_keywords = {
            ContentCategory.TECHNOLOGY: [
                '技术', '编程', '代码', '开发', '算法', 'AI', '人工智能',
                '机器学习', '深度学习', '软件', '硬件', '科技'
            ],
            ContentCategory.ENTERTAINMENT: [
                '娱乐', '游戏', '电影', '音乐', '动漫', '综艺', '明星',
                '影视', '剧集', '电视剧'
            ],
            ContentCategory.EDUCATION: [
                '教育', '学习', '教程', '课程', '知识', '讲解', '科普',
                '入门', '进阶', '教学'
            ],
            ContentCategory.NEWS: [
                '新闻', '时事', '热点', '资讯', '报道', '事件', '动态'
            ],
            ContentCategory.LIFESTYLE: [
                '生活', '美食', '旅游', '健康', '运动', '时尚', '美妆',
                '摄影', 'vlog', '日常'
            ]
        }
    
    def _categorize_content(self, title: str, summary: str | None = None) -> ContentCategory:
        """
        Categorize content based on title and summary.
        
        Args:
            title: Content title
            summary: Optional content summary
            
        Returns:
            Detected category
        """
        text = title.lower()
        if summary:
            text += " " + summary.lower()
        
        # Count keyword matches for each category
        category_scores: dict[ContentCategory, int] = {}
        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                category_scores[category] = score
        
        # Return category with highest score
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        
        return ContentCategory.OTHER
    
    def _calculate_importance(
        self,
        published: datetime | None,
        has_summary: bool,
        source: ContentSource
    ) -> float:
        """
        Calculate importance score for content.
        
        Args:
            published: Publication datetime
            has_summary: Whether content has a summary
            source: Content source
            
        Returns:
            Importance score (0.0 to 1.0)
        """
        score = 0.5  # Base score
        
        # Recency bonus (up to +0.3)
        if published:
            age_hours = (datetime.now() - published).total_seconds() / 3600
            if age_hours < 24:
                score += 0.3 * (1 - age_hours / 24)
            elif age_hours < 72:
                score += 0.1
        
        # Summary bonus (+0.1)
        if has_summary:
            score += 0.1
        
        # Source bonus (Bilibili slightly higher as it's video content)
        if source == ContentSource.BILIBILI:
            score += 0.05
        
        return min(1.0, score)
    
    def collect_bilibili_content(
        self,
        reports: list[BilibiliMonitorReport],
        since: datetime | None = None
    ) -> list[ContentItem]:
        """
        Collect content from Bilibili monitor reports.
        
        Args:
            reports: List of Bilibili monitor reports
            since: Only include content published after this time
            
        Returns:
            List of content items
        """
        items: list[ContentItem] = []
        
        for report in reports:
            for video in report.new_videos:
                # Filter by time if specified
                if since and video.published and video.published < since:
                    continue
                
                # Create content item
                category = self._categorize_content(video.title, video.description)
                importance = self._calculate_importance(
                    video.published,
                    bool(video.description),
                    ContentSource.BILIBILI
                )
                
                item = ContentItem(
                    title=video.title,
                    url=f"https://www.bilibili.com/video/{video.bvid}",
                    source=ContentSource.BILIBILI,
                    published=video.published,
                    author=report.up_name,
                    summary=video.description[:200] if video.description else None,
                    category=category,
                    importance_score=importance,
                    tags=[],
                    source_data={
                        'bvid': video.bvid,
                        'mid': report.mid,
                        'up_name': report.up_name,
                        'view_count': video.view_count,
                        'like_count': video.like_count
                    }
                )
                items.append(item)
        
        logger.info(f"Collected {len(items)} items from Bilibili")
        return items
    
    def collect_zhihu_content(
        self,
        reports: list[ZhihuMonitorReport],
        since: datetime | None = None,
        bilibili_links_only: bool = False
    ) -> list[ContentItem]:
        """
        Collect content from Zhihu RSS reports.
        
        Args:
            reports: List of Zhihu monitor reports
            since: Only include content published after this time
            bilibili_links_only: Only include items with Bilibili links
            
        Returns:
            List of content items
        """
        items: list[ContentItem] = []
        
        for report in reports:
            for feed_item in report.new_items:
                # Filter by time if specified
                if since and feed_item.published and feed_item.published < since:
                    continue
                
                # Filter by Bilibili links if specified
                if bilibili_links_only and not feed_item.bilibili_links:
                    continue
                
                # Create content item
                category = self._categorize_content(feed_item.title, feed_item.summary)
                importance = self._calculate_importance(
                    feed_item.published,
                    bool(feed_item.summary),
                    ContentSource.ZHIHU
                )
                
                # Boost importance if it has Bilibili links
                if feed_item.bilibili_links:
                    importance = min(1.0, importance + 0.1)
                
                item = ContentItem(
                    title=feed_item.title,
                    url=feed_item.link,
                    source=ContentSource.ZHIHU,
                    published=feed_item.published,
                    author=feed_item.author,
                    summary=feed_item.summary[:200] if feed_item.summary else None,
                    category=category,
                    importance_score=importance,
                    tags=[],
                    source_data={
                        'feed_url': report.feed_url,
                        'feed_name': report.feed_name,
                        'bilibili_links': feed_item.bilibili_links or [],
                        'guid': feed_item.guid
                    }
                )
                items.append(item)
        
        logger.info(f"Collected {len(items)} items from Zhihu")
        return items
    
    def aggregate_all(
        self,
        bilibili_reports: list[BilibiliMonitorReport] | None = None,
        zhihu_reports: list[ZhihuMonitorReport] | None = None,
        since: datetime | None = None,
        min_importance: float = 0.3,
        max_items_per_category: int = 10
    ) -> DailyReport:
        """
        Aggregate content from all sources into a daily report.
        
        Args:
            bilibili_reports: Bilibili monitor reports
            zhihu_reports: Zhihu RSS reports
            since: Only include content published after this time
            min_importance: Minimum importance score to include
            max_items_per_category: Maximum items per category
            
        Returns:
            Daily report with aggregated content
        """
        # Create report
        report_date = datetime.now()
        report = DailyReport(
            report_date=report_date,
            title=f"每日内容汇总 - {report_date.strftime('%Y年%m月%d日')}",
            generation_time=datetime.now()
        )
        
        # Collect content from all sources
        all_items: list[ContentItem] = []
        
        if bilibili_reports:
            all_items.extend(self.collect_bilibili_content(bilibili_reports, since))
        
        if zhihu_reports:
            all_items.extend(self.collect_zhihu_content(zhihu_reports, since))
        
        # Filter by importance
        all_items = [item for item in all_items if item.importance_score >= min_importance]
        
        # Sort by importance (descending)
        all_items.sort(key=lambda x: x.importance_score, reverse=True)
        
        # Group by category and limit items per category
        category_items: dict[ContentCategory, list[ContentItem]] = {}
        for item in all_items:
            if item.category not in category_items:
                category_items[item.category] = []
            
            if len(category_items[item.category]) < max_items_per_category:
                category_items[item.category].append(item)
        
        # Add items to report
        for item in all_items:
            if item in category_items.get(item.category, []):
                report.add_item(item)
        
        logger.info(
            f"Aggregated {report.total_items} items "
            f"({report.bilibili_items} Bilibili, {report.zhihu_items} Zhihu)"
        )
        
        return report

