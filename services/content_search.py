"""
Content search and filtering service.

Provides powerful search and filtering capabilities for monitored content,
including keyword search, category filtering, source filtering, and date range queries.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Literal, Sequence
from dataclasses import dataclass, field

from models.report import ContentItem, ContentSource, ContentCategory


logger = logging.getLogger(__name__)


@dataclass
class SearchQuery:
    """Search query parameters."""
    
    # Text search
    keywords: list[str] = field(default_factory=list)
    search_in: list[Literal["title", "summary", "author"]] = field(default_factory=lambda: ["title", "summary"])
    case_sensitive: bool = False
    
    # Filters
    categories: list[ContentCategory] = field(default_factory=list)
    sources: list[ContentSource] = field(default_factory=list)
    min_importance: float | None = None
    max_importance: float | None = None
    
    # Date range
    start_date: datetime | None = None
    end_date: datetime | None = None
    
    # Sorting
    sort_by: Literal["date", "importance", "relevance"] = "relevance"
    sort_order: Literal["asc", "desc"] = "desc"
    
    # Pagination
    limit: int = 20
    offset: int = 0


@dataclass
class SearchResult:
    """Search result with relevance scoring."""
    
    item: ContentItem
    relevance_score: float = 0.0
    matched_fields: list[str] = field(default_factory=list)
    
    def __lt__(self, other: SearchResult) -> bool:
        """Compare by relevance score for sorting."""
        return self.relevance_score < other.relevance_score


class ContentSearchEngine:
    """Search engine for content items with advanced filtering."""
    
    def __init__(self):
        """Initialize search engine."""
        self.content_index: list[ContentItem] = []
    
    def index_content(self, items: list[ContentItem]):
        """
        Add content items to the search index.
        
        Args:
            items: Content items to index
        """
        self.content_index.extend(items)
        logger.info(f"Indexed {len(items)} content items (total: {len(self.content_index)})")
    
    def clear_index(self):
        """Clear all indexed content."""
        self.content_index.clear()
        logger.info("Search index cleared")
    
    def remove_old_content(self, days: int = 30):
        """
        Remove content older than specified days.
        
        Args:
            days: Number of days to keep
        """
        cutoff = datetime.now() - timedelta(days=days)
        original_count = len(self.content_index)
        
        self.content_index = [
            item for item in self.content_index
            if item.published and item.published >= cutoff
        ]
        
        removed = original_count - len(self.content_index)
        if removed > 0:
            logger.info(f"Removed {removed} old content items (older than {days} days)")
    
    def _calculate_relevance(
        self,
        item: ContentItem,
        keywords: list[str],
        search_in: Sequence[str],
        case_sensitive: bool
    ) -> tuple[float, list[str]]:
        """
        Calculate relevance score for an item based on keyword matches.
        
        Args:
            item: Content item
            keywords: Search keywords
            search_in: Fields to search in
            case_sensitive: Whether search is case-sensitive
            
        Returns:
            Tuple of (relevance_score, matched_fields)
        """
        if not keywords:
            return 1.0, []
        
        score = 0.0
        matched_fields = []
        
        # Prepare search text
        search_texts = {}
        if "title" in search_in and item.title:
            search_texts["title"] = item.title if case_sensitive else item.title.lower()
        if "summary" in search_in and item.summary:
            search_texts["summary"] = item.summary if case_sensitive else item.summary.lower()
        if "author" in search_in and item.author:
            search_texts["author"] = item.author if case_sensitive else item.author.lower()
        
        # Prepare keywords
        search_keywords = keywords if case_sensitive else [k.lower() for k in keywords]
        
        # Calculate score based on matches
        for field_name, text in search_texts.items():
            field_score = 0.0
            field_matched = False
            
            for keyword in search_keywords:
                # Count occurrences
                count = text.count(keyword)
                if count > 0:
                    field_matched = True
                    # Weight by field importance
                    field_weight = {"title": 3.0, "summary": 1.5, "author": 1.0}.get(field_name, 1.0)
                    # Add score (diminishing returns for multiple occurrences)
                    field_score += field_weight * (1.0 + 0.5 * min(count - 1, 3))
            
            if field_matched:
                matched_fields.append(field_name)
                score += field_score
        
        # Normalize score
        max_possible_score = len(keywords) * 3.0  # Max if all keywords match in title
        normalized_score = min(1.0, score / max_possible_score) if max_possible_score > 0 else 0.0
        
        return normalized_score, matched_fields
    
    def _matches_filters(self, item: ContentItem, query: SearchQuery) -> bool:
        """
        Check if item matches filter criteria.
        
        Args:
            item: Content item
            query: Search query with filters
            
        Returns:
            True if item matches all filters
        """
        # Category filter
        if query.categories and item.category not in query.categories:
            return False
        
        # Source filter
        if query.sources and item.source not in query.sources:
            return False
        
        # Importance filter
        if query.min_importance is not None and item.importance_score < query.min_importance:
            return False
        if query.max_importance is not None and item.importance_score > query.max_importance:
            return False
        
        # Date range filter
        if item.published:
            if query.start_date and item.published < query.start_date:
                return False
            if query.end_date and item.published > query.end_date:
                return False
        
        return True
    
    def search(self, query: SearchQuery) -> list[SearchResult]:
        """
        Search content with advanced filtering and ranking.
        
        Args:
            query: Search query parameters
            
        Returns:
            List of search results sorted by relevance
        """
        results: list[SearchResult] = []
        
        # Filter and score items
        for item in self.content_index:
            # Apply filters
            if not self._matches_filters(item, query):
                continue
            
            # Calculate relevance
            relevance, matched_fields = self._calculate_relevance(
                item,
                query.keywords,
                query.search_in,
                query.case_sensitive
            )
            
            # Skip items with no keyword matches (if keywords provided)
            if query.keywords and relevance == 0.0:
                continue
            
            # Create result
            result = SearchResult(
                item=item,
                relevance_score=relevance,
                matched_fields=matched_fields
            )
            results.append(result)
        
        # Sort results
        if query.sort_by == "relevance":
            results.sort(key=lambda r: r.relevance_score, reverse=(query.sort_order == "desc"))
        elif query.sort_by == "importance":
            results.sort(key=lambda r: r.item.importance_score, reverse=(query.sort_order == "desc"))
        elif query.sort_by == "date":
            results.sort(
                key=lambda r: r.item.published or datetime.min,
                reverse=(query.sort_order == "desc")
            )
        
        # Apply pagination
        start = query.offset
        end = start + query.limit
        paginated_results = results[start:end]
        
        logger.info(
            f"Search completed: {len(results)} results found, "
            f"returning {len(paginated_results)} (offset={query.offset}, limit={query.limit})"
        )
        
        return paginated_results
    
    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about indexed content.
        
        Returns:
            Dictionary with statistics
        """
        if not self.content_index:
            return {
                "total_items": 0,
                "by_source": {},
                "by_category": {},
                "date_range": None
            }
        
        # Count by source
        by_source: dict[str, int] = {}
        for item in self.content_index:
            source = item.source.value
            by_source[source] = by_source.get(source, 0) + 1

        # Count by category
        by_category: dict[str, int] = {}
        for item in self.content_index:
            category = item.category.value
            by_category[category] = by_category.get(category, 0) + 1

        # Date range
        items_with_dates = [item for item in self.content_index if item.published]
        date_range: dict[str, str] | None
        if items_with_dates:
            dates = [item.published for item in items_with_dates if item.published is not None]
            if dates:
                date_range = {
                    "earliest": min(dates).isoformat(),
                    "latest": max(dates).isoformat()
                }
            else:
                date_range = None
        else:
            date_range = None
        
        return {
            "total_items": len(self.content_index),
            "by_source": by_source,
            "by_category": by_category,
            "date_range": date_range
        }

