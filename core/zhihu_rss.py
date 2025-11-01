"""
Zhihu RSS feed client.

Fetches and parses Zhihu RSS feeds, extracting Bilibili video links.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
import httpx

try:
    import feedparser  # type: ignore
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

from models.zhihu import ZhihuFeedItem, ZhihuFeedConfig, ZhihuMonitorReport, ZhihuMonitorState
from utils.link_extractor import extract_bilibili_links, deduplicate_links


class ZhihuRSSClient:
    """Client for fetching and parsing Zhihu RSS feeds."""
    
    def __init__(self, timeout: float = 30.0):
        """
        Initialize Zhihu RSS client.
        
        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        
        if not FEEDPARSER_AVAILABLE:
            raise ImportError(
                "feedparser is required for Zhihu RSS support. "
                "Install it with: pip install feedparser"
            )
    
    async def fetch_feed(self, feed_url: str) -> dict[str, Any]:
        """
        Fetch and parse RSS feed.
        
        Args:
            feed_url: URL of the RSS feed
            
        Returns:
            Parsed feed data from feedparser
            
        Raises:
            httpx.HTTPError: If feed fetch fails
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
            
            # Parse feed in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            feed_data = await loop.run_in_executor(
                None,
                feedparser.parse,
                response.text
            )
            
            return feed_data
    
    def parse_feed_item(
        self,
        entry: Any,
        extract_bilibili: bool = True
    ) -> ZhihuFeedItem:
        """
        Parse a single feed entry into ZhihuFeedItem.
        
        Args:
            entry: Feed entry from feedparser
            extract_bilibili: Whether to extract Bilibili links
            
        Returns:
            Parsed ZhihuFeedItem
        """
        # Extract basic fields
        title = entry.get('title', '')
        link = entry.get('link', '')
        guid = entry.get('id') or entry.get('guid', '')
        author = entry.get('author', '')
        
        # Extract published date
        published = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                from time import struct_time
                if isinstance(entry.published_parsed, struct_time):
                    published = datetime(*entry.published_parsed[:6])
            except (ValueError, TypeError):
                pass
        
        # Extract content
        summary = entry.get('summary', '')
        content = ''
        
        # Try to get full content
        if hasattr(entry, 'content') and entry.content:
            content = entry.content[0].get('value', '') if entry.content else ''
        elif hasattr(entry, 'description'):
            content = entry.description
        
        # Use content or summary
        full_content = content or summary
        
        # Extract Bilibili links if requested
        bilibili_links = []
        if extract_bilibili and full_content:
            bilibili_links = extract_bilibili_links(full_content)
            bilibili_links = deduplicate_links(bilibili_links)
        
        return ZhihuFeedItem(
            title=title,
            link=link,
            published=published,
            author=author,
            summary=summary[:500] if summary else None,  # Limit summary length
            content=full_content[:2000] if full_content else None,  # Limit content length
            guid=guid,
            bilibili_links=bilibili_links
        )
    
    async def check_feed(
        self,
        config: ZhihuFeedConfig,
        state: ZhihuMonitorState
    ) -> ZhihuMonitorReport:
        """
        Check a Zhihu RSS feed for new items.
        
        Args:
            config: Feed configuration
            state: Monitor state for tracking processed items
            
        Returns:
            Monitor report with new items
        """
        check_time = datetime.now()
        feed_state = state.get_or_create_feed_state(config.feed_url, config.name)
        
        try:
            # Fetch and parse feed
            feed_data = await self.fetch_feed(config.feed_url)
            
            # Check for feed errors
            if hasattr(feed_data, 'bozo') and feed_data.bozo:
                error_msg = str(feed_data.get('bozo_exception', 'Unknown feed parsing error'))
                feed_state.last_error = error_msg
                feed_state.error_count += 1
                return ZhihuMonitorReport(
                    feed_url=config.feed_url,
                    feed_name=config.name,
                    check_time=check_time,
                    error=error_msg
                )
            
            # Parse entries
            new_items = []
            entries = feed_data.get('entries', [])
            
            for entry in entries[:config.max_items]:
                item = self.parse_feed_item(entry, config.check_bilibili_links)
                item_id = item.get_id()
                
                if feed_state.is_item_new(item_id):
                    new_items.append(item)
                    feed_state.mark_item_processed(item_id)
            
            # Update state
            feed_state.last_check_time = check_time
            feed_state.last_error = None
            feed_state.error_count = 0
            
            return ZhihuMonitorReport(
                feed_url=config.feed_url,
                feed_name=config.name,
                check_time=check_time,
                new_items=new_items
            )
            
        except Exception as e:
            error_msg = f"Failed to check feed: {str(e)}"
            feed_state.last_error = error_msg
            feed_state.error_count += 1
            feed_state.last_check_time = check_time
            
            return ZhihuMonitorReport(
                feed_url=config.feed_url,
                feed_name=config.name,
                check_time=check_time,
                error=error_msg
            )
    
    async def check_multiple_feeds(
        self,
        configs: list[ZhihuFeedConfig],
        state: ZhihuMonitorState,
        delay_between_checks: float = 1.0
    ) -> list[ZhihuMonitorReport]:
        """
        Check multiple Zhihu RSS feeds.
        
        Args:
            configs: List of feed configurations
            state: Monitor state
            delay_between_checks: Delay between feed checks in seconds
            
        Returns:
            List of monitor reports
        """
        reports = []
        
        for config in configs:
            if not config.enabled:
                continue
            
            report = await self.check_feed(config, state)
            reports.append(report)
            
            # Add delay between checks to avoid rate limiting
            if delay_between_checks > 0:
                await asyncio.sleep(delay_between_checks)
        
        return reports


def get_reports_with_new_items(reports: list[ZhihuMonitorReport]) -> list[ZhihuMonitorReport]:
    """
    Filter reports to only those with new items.
    
    Args:
        reports: List of monitor reports
        
    Returns:
        Filtered list of reports with new items
    """
    return [r for r in reports if r.has_new_items()]


def get_reports_with_bilibili_links(reports: list[ZhihuMonitorReport]) -> list[ZhihuMonitorReport]:
    """
    Filter reports to only those with Bilibili links.
    
    Args:
        reports: List of monitor reports
        
    Returns:
        Filtered list of reports with Bilibili links
    """
    return [r for r in reports if r.has_bilibili_links()]

