"""
State management for Zhihu RSS feed monitoring.

Handles persistence and retrieval of Zhihu monitoring state.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from models.zhihu import ZhihuMonitorState, ZhihuFeedState


class ZhihuStateManager:
    """Manages Zhihu RSS monitoring state persistence."""

    def __init__(self, state_file_path: Path):
        """
        Initialize Zhihu state manager.
        
        Args:
            state_file_path: Path to the state file
        """
        self.state_file_path = state_file_path
        self._state: ZhihuMonitorState | None = None

    def load_state(self) -> ZhihuMonitorState:
        """
        Load state from file.
        
        Returns:
            ZhihuMonitorState object
        """
        if self._state is None:
            self._state = self._load_from_file()
        return self._state

    def _load_from_file(self) -> ZhihuMonitorState:
        """Load state from JSON file."""
        if not self.state_file_path.exists():
            return ZhihuMonitorState()
        
        try:
            with open(self.state_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return ZhihuMonitorState.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # If state file is corrupted, start fresh
            print(f"Warning: Failed to load Zhihu state file: {e}. Starting with empty state.")
            return ZhihuMonitorState()

    def save_state(self) -> None:
        """Save current state to file."""
        if self._state is not None:
            self._save_to_file(self._state)

    def _save_to_file(self, state: ZhihuMonitorState) -> None:
        """Save state to JSON file."""
        # Ensure directory exists
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temporary file first, then rename for atomicity
        temp_path = self.state_file_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
            
            # Atomic rename
            temp_path.replace(self.state_file_path)
        except Exception as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise e

    def get_feed_state(self, feed_url: str, name: str | None = None) -> ZhihuFeedState:
        """
        Get or create state for a feed.
        
        Args:
            feed_url: Feed URL
            name: Optional feed name
            
        Returns:
            ZhihuFeedState object
        """
        state = self.load_state()
        return state.get_or_create_feed_state(feed_url, name)

    def update_feed_state(
        self,
        feed_url: str,
        processed_items: list[str] | None = None,
        error: str | None = None
    ) -> None:
        """
        Update state for a feed.
        
        Args:
            feed_url: Feed URL
            processed_items: List of processed item IDs to add
            error: Error message if check failed
        """
        state = self.load_state()
        feed_state = state.get_or_create_feed_state(feed_url)
        
        feed_state.last_check_time = datetime.now()
        
        if processed_items:
            for item_id in processed_items:
                feed_state.mark_item_processed(item_id)
        
        if error is not None:
            feed_state.last_error = error
            feed_state.error_count += 1
        else:
            feed_state.last_error = None
            feed_state.error_count = 0
        
        self.save_state()

    def is_item_new(self, feed_url: str, item_id: str) -> bool:
        """
        Check if an item is new (not processed yet).
        
        Args:
            feed_url: Feed URL
            item_id: Item ID
            
        Returns:
            True if item is new, False otherwise
        """
        feed_state = self.get_feed_state(feed_url)
        return feed_state.is_item_new(item_id)

    def mark_items_processed(self, feed_url: str, item_ids: list[str]) -> None:
        """
        Mark multiple items as processed.
        
        Args:
            feed_url: Feed URL
            item_ids: List of item IDs
        """
        self.update_feed_state(feed_url, processed_items=item_ids)

    def get_last_check_time(self, feed_url: str) -> datetime | None:
        """
        Get the last check time for a feed.
        
        Args:
            feed_url: Feed URL
            
        Returns:
            Last check time as datetime, or None if never checked
        """
        feed_state = self.get_feed_state(feed_url)
        return feed_state.last_check_time

    def get_error_count(self, feed_url: str) -> int:
        """
        Get the error count for a feed.
        
        Args:
            feed_url: Feed URL
            
        Returns:
            Number of consecutive errors
        """
        feed_state = self.get_feed_state(feed_url)
        return feed_state.error_count

    def cleanup_old_processed_items(self, feed_url: str, keep_count: int = 1000) -> None:
        """
        Clean up old processed items to prevent state file from growing too large.
        
        Args:
            feed_url: Feed URL
            keep_count: Number of recent processed items to keep
        """
        state = self.load_state()
        feed_state = state.get_or_create_feed_state(feed_url)
        
        if len(feed_state.processed_items) > keep_count:
            # Keep only the most recent ones
            feed_state.processed_items = feed_state.processed_items[-keep_count:]
            self.save_state()

