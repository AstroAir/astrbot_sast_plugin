"""
State management for Bilibili UP master monitoring.

Handles persistence and retrieval of monitoring state.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.bilibili import MonitorState, UPMasterState, VideoInfo

from models.bilibili import MonitorState


class StateManager:
    """Manages monitoring state persistence."""

    def __init__(self, state_file_path: Path):
        """Initialize state manager.
        
        Args:
            state_file_path: Path to the state file
        """
        self.state_file_path = state_file_path
        self._state: MonitorState | None = None

    def load_state(self) -> MonitorState:
        """Load state from file.
        
        Returns:
            MonitorState object
        """
        if self._state is None:
            self._state = MonitorState.load_from_file(self.state_file_path)
        return self._state

    def save_state(self) -> None:
        """Save current state to file."""
        if self._state is not None:
            self._state.save_to_file(self.state_file_path)

    def get_up_state(self, mid: str) -> UPMasterState:
        """Get or create state for an UP master.
        
        Args:
            mid: UP master's mid
            
        Returns:
            UPMasterState object
        """
        state = self.load_state()
        return state.get_or_create_up_state(mid)

    def update_up_state(
        self,
        mid: str,
        last_video_bvid: str | None = None,
        last_video_aid: int | None = None,
        processed_videos: list[str] | None = None
    ) -> None:
        """Update state for an UP master.
        
        Args:
            mid: UP master's mid
            last_video_bvid: Latest video's bvid
            last_video_aid: Latest video's aid
            processed_videos: List of processed video bvids to add
        """
        state = self.load_state()
        up_state = state.get_or_create_up_state(mid)
        
        up_state.last_check_time = int(datetime.now().timestamp())
        
        if last_video_bvid is not None:
            up_state.last_video_bvid = last_video_bvid
        
        if last_video_aid is not None:
            up_state.last_video_aid = last_video_aid
        
        if processed_videos:
            for bvid in processed_videos:
                up_state.mark_video_processed(bvid)
        
        self.save_state()

    def is_video_new(self, mid: str, bvid: str) -> bool:
        """Check if a video is new (not processed yet).
        
        Args:
            mid: UP master's mid
            bvid: Video's bvid
            
        Returns:
            True if video is new, False otherwise
        """
        up_state = self.get_up_state(mid)
        return not up_state.is_video_processed(bvid)

    def mark_videos_processed(self, mid: str, bvids: list[str]) -> None:
        """Mark multiple videos as processed.
        
        Args:
            mid: UP master's mid
            bvids: List of video bvids
        """
        self.update_up_state(mid, processed_videos=bvids)

    def get_last_check_time(self, mid: str) -> datetime | None:
        """Get the last check time for an UP master.
        
        Args:
            mid: UP master's mid
            
        Returns:
            Last check time as datetime, or None if never checked
        """
        up_state = self.get_up_state(mid)
        if up_state.last_check_time > 0:
            return datetime.fromtimestamp(up_state.last_check_time)
        return None

    def cleanup_old_processed_videos(self, mid: str, keep_count: int = 100) -> None:
        """Clean up old processed videos to prevent state file from growing too large.
        
        Args:
            mid: UP master's mid
            keep_count: Number of recent processed videos to keep
        """
        state = self.load_state()
        up_state = state.get_or_create_up_state(mid)
        
        if len(up_state.processed_videos) > keep_count:
            # Keep only the most recent ones (this is a simple approach)
            # In a real implementation, you might want to track timestamps
            processed_list = list(up_state.processed_videos)
            up_state.processed_videos = set(processed_list[-keep_count:])
            self.save_state()

