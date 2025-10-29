"""
Data models for Zhihu RSS feed monitoring.

Defines structures for Zhihu feed items, configurations, and state management.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class ZhihuFeedItem:
    """Represents a single item from a Zhihu RSS feed."""
    
    title: str
    link: str
    published: datetime | None = None
    author: str | None = None
    summary: str | None = None
    content: str | None = None
    guid: str | None = None
    bilibili_links: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        if self.published:
            data['published'] = self.published.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ZhihuFeedItem:
        """Create from dictionary."""
        if 'published' in data and data['published']:
            if isinstance(data['published'], str):
                data['published'] = datetime.fromisoformat(data['published'])
        return cls(**data)
    
    def get_id(self) -> str:
        """Get unique identifier for this item."""
        return self.guid or self.link


@dataclass
class ZhihuFeedConfig:
    """Configuration for a Zhihu RSS feed to monitor."""
    
    feed_url: str
    name: str | None = None
    enabled: bool = True
    check_bilibili_links: bool = True
    max_items: int = 10
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ZhihuFeedConfig:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ZhihuFeedState:
    """State tracking for a single Zhihu RSS feed."""
    
    feed_url: str
    name: str | None = None
    processed_items: list[str] = field(default_factory=list)
    last_check_time: datetime | None = None
    last_error: str | None = None
    error_count: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        if self.last_check_time:
            data['last_check_time'] = self.last_check_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ZhihuFeedState:
        """Create from dictionary."""
        if 'last_check_time' in data and data['last_check_time']:
            if isinstance(data['last_check_time'], str):
                data['last_check_time'] = datetime.fromisoformat(data['last_check_time'])
        return cls(**data)
    
    def is_item_new(self, item_id: str) -> bool:
        """Check if an item has been processed."""
        return item_id not in self.processed_items
    
    def mark_item_processed(self, item_id: str):
        """Mark an item as processed."""
        if item_id not in self.processed_items:
            self.processed_items.append(item_id)
            # Keep only last 1000 items to prevent unbounded growth
            if len(self.processed_items) > 1000:
                self.processed_items = self.processed_items[-1000:]


@dataclass
class ZhihuMonitorState:
    """Global state for Zhihu RSS monitoring."""
    
    feeds: dict[str, ZhihuFeedState] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'feeds': {url: state.to_dict() for url, state in self.feeds.items()}
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ZhihuMonitorState:
        """Create from dictionary."""
        feeds = {}
        if 'feeds' in data:
            for url, state_data in data['feeds'].items():
                feeds[url] = ZhihuFeedState.from_dict(state_data)
        return cls(feeds=feeds)
    
    def get_or_create_feed_state(self, feed_url: str, name: str | None = None) -> ZhihuFeedState:
        """Get existing feed state or create new one."""
        if feed_url not in self.feeds:
            self.feeds[feed_url] = ZhihuFeedState(feed_url=feed_url, name=name)
        return self.feeds[feed_url]


@dataclass
class ZhihuMonitorReport:
    """Report from a Zhihu RSS feed check."""
    
    feed_url: str
    feed_name: str | None
    check_time: datetime
    new_items: list[ZhihuFeedItem] = field(default_factory=list)
    error: str | None = None
    
    def has_new_items(self) -> bool:
        """Check if report contains new items."""
        return len(self.new_items) > 0
    
    def has_bilibili_links(self) -> bool:
        """Check if any new items contain Bilibili links."""
        return any(item.bilibili_links for item in self.new_items)
    
    def get_all_bilibili_links(self) -> list[tuple[str, list[str]]]:
        """Get all Bilibili links with their source items.
        
        Returns:
            List of (item_title, bilibili_links) tuples
        """
        result = []
        for item in self.new_items:
            if item.bilibili_links:
                result.append((item.title, item.bilibili_links))
        return result
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'feed_url': self.feed_url,
            'feed_name': self.feed_name,
            'check_time': self.check_time.isoformat(),
            'new_items': [item.to_dict() for item in self.new_items],
            'error': self.error
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ZhihuMonitorReport:
        """Create from dictionary."""
        check_time = data['check_time']
        if isinstance(check_time, str):
            check_time = datetime.fromisoformat(check_time)
        
        new_items = []
        if 'new_items' in data:
            new_items = [ZhihuFeedItem.from_dict(item) for item in data['new_items']]
        
        return cls(
            feed_url=data['feed_url'],
            feed_name=data.get('feed_name'),
            check_time=check_time,
            new_items=new_items,
            error=data.get('error')
        )

