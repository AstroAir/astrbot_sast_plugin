"""
Data models for AI-powered daily reports.

Defines structures for aggregating content from multiple sources and generating
intelligent daily summaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Literal
from enum import Enum


class ContentSource(str, Enum):
    """Source of content for daily reports."""
    BILIBILI = "bilibili"
    ZHIHU = "zhihu"
    OTHER = "other"


class ContentCategory(str, Enum):
    """Category of content."""
    TECHNOLOGY = "technology"
    ENTERTAINMENT = "entertainment"
    EDUCATION = "education"
    NEWS = "news"
    LIFESTYLE = "lifestyle"
    OTHER = "other"


@dataclass
class ContentItem:
    """A single piece of content for the daily report."""
    
    title: str
    url: str
    source: ContentSource
    published: datetime | None = None
    author: str | None = None
    summary: str | None = None
    category: ContentCategory = ContentCategory.OTHER
    importance_score: float = 0.5  # 0.0 to 1.0
    tags: list[str] = field(default_factory=list)
    
    # Source-specific data
    source_data: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        if self.published:
            data['published'] = self.published.isoformat()
        data['source'] = self.source.value
        data['category'] = self.category.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentItem:
        """Create from dictionary."""
        if 'published' in data and data['published']:
            if isinstance(data['published'], str):
                data['published'] = datetime.fromisoformat(data['published'])
        
        if 'source' in data and isinstance(data['source'], str):
            data['source'] = ContentSource(data['source'])
        
        if 'category' in data and isinstance(data['category'], str):
            data['category'] = ContentCategory(data['category'])
        
        return cls(**data)


@dataclass
class CategorySection:
    """A section of the daily report grouped by category."""
    
    category: ContentCategory
    items: list[ContentItem] = field(default_factory=list)
    ai_summary: str | None = None
    
    def get_item_count(self) -> int:
        """Get number of items in this section."""
        return len(self.items)
    
    def get_average_importance(self) -> float:
        """Get average importance score of items."""
        if not self.items:
            return 0.0
        return sum(item.importance_score for item in self.items) / len(self.items)


@dataclass
class DailyReportConfig:
    """Configuration for daily report generation."""
    
    enabled: bool = True
    generation_time: str = "09:00"  # Time to generate report (HH:MM)
    
    # Content sources
    include_bilibili: bool = True
    include_zhihu: bool = True
    
    # Report options
    categorize_content: bool = True
    generate_ai_summary: bool = True
    highlight_important: bool = True
    max_items_per_category: int = 10
    min_importance_score: float = 0.3
    
    # Output options
    output_format: Literal["markdown", "html", "text"] = "markdown"
    include_statistics: bool = True
    include_trending: bool = True
    
    # Delivery
    delivery_targets: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailyReportConfig:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class DailyReport:
    """A complete daily report with aggregated content."""
    
    report_date: datetime
    title: str
    sections: list[CategorySection] = field(default_factory=list)
    executive_summary: str | None = None
    trending_topics: list[str] = field(default_factory=list)
    
    # Statistics
    total_items: int = 0
    bilibili_items: int = 0
    zhihu_items: int = 0
    
    # Metadata
    generation_time: datetime | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'report_date': self.report_date.isoformat(),
            'title': self.title,
            'sections': [
                {
                    'category': section.category.value,
                    'items': [item.to_dict() for item in section.items],
                    'ai_summary': section.ai_summary
                }
                for section in self.sections
            ],
            'executive_summary': self.executive_summary,
            'trending_topics': self.trending_topics,
            'total_items': self.total_items,
            'bilibili_items': self.bilibili_items,
            'zhihu_items': self.zhihu_items,
            'generation_time': self.generation_time.isoformat() if self.generation_time else None
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DailyReport:
        """Create from dictionary."""
        report_date = data['report_date']
        if isinstance(report_date, str):
            report_date = datetime.fromisoformat(report_date)
        
        generation_time = data.get('generation_time')
        if generation_time and isinstance(generation_time, str):
            generation_time = datetime.fromisoformat(generation_time)
        
        sections = []
        for section_data in data.get('sections', []):
            category = ContentCategory(section_data['category'])
            items = [ContentItem.from_dict(item_data) for item_data in section_data.get('items', [])]
            sections.append(CategorySection(
                category=category,
                items=items,
                ai_summary=section_data.get('ai_summary')
            ))
        
        return cls(
            report_date=report_date,
            title=data['title'],
            sections=sections,
            executive_summary=data.get('executive_summary'),
            trending_topics=data.get('trending_topics', []),
            total_items=data.get('total_items', 0),
            bilibili_items=data.get('bilibili_items', 0),
            zhihu_items=data.get('zhihu_items', 0),
            generation_time=generation_time
        )
    
    def get_section(self, category: ContentCategory) -> CategorySection | None:
        """Get section by category."""
        for section in self.sections:
            if section.category == category:
                return section
        return None
    
    def add_item(self, item: ContentItem):
        """Add an item to the appropriate section."""
        section = self.get_section(item.category)
        if not section:
            section = CategorySection(category=item.category)
            self.sections.append(section)
        
        section.items.append(item)
        self.total_items += 1
        
        if item.source == ContentSource.BILIBILI:
            self.bilibili_items += 1
        elif item.source == ContentSource.ZHIHU:
            self.zhihu_items += 1
    
    def get_all_items(self) -> list[ContentItem]:
        """Get all items from all sections."""
        items = []
        for section in self.sections:
            items.extend(section.items)
        return items
    
    def get_high_importance_items(self, threshold: float = 0.7) -> list[ContentItem]:
        """Get items with importance score above threshold."""
        return [
            item for item in self.get_all_items()
            if item.importance_score >= threshold
        ]

