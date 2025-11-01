"""
Data models for Bilibili UP master monitoring plugin.

Defines configuration and state management structures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import json
from pathlib import Path


@dataclass(slots=True)
class UPMasterConfig:
    """Configuration for a single UP master to monitor."""
    mid: str
    name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UPMasterConfig:
        return cls(
            mid=str(data.get("mid", "")),
            name=str(data.get("name", ""))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mid": self.mid,
            "name": self.name
        }


@dataclass(slots=True)
class VideoInfo:
    """Information about a single video."""
    aid: int | None
    bvid: str | None
    title: str
    desc: str
    publish_time: int | None  # Unix timestamp
    play_count: int | None
    like_count: int | None = None
    coin_count: int | None = None
    favorite_count: int | None = None
    share_count: int | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> VideoInfo:
        """Create VideoInfo from Bilibili API response."""
        return cls(
            aid=data.get("aid"),
            bvid=data.get("bvid"),
            title=data.get("title", ""),
            desc=data.get("description", ""),
            publish_time=data.get("publish_time") or data.get("pubdate"),
            play_count=data.get("play_count") or data.get("play"),
            like_count=data.get("like_count") or data.get("like"),
            coin_count=data.get("coin_count") or data.get("coin"),
            favorite_count=data.get("favorite_count") or data.get("favorite"),
            share_count=data.get("share_count") or data.get("share")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "aid": self.aid,
            "bvid": self.bvid,
            "title": self.title,
            "desc": self.desc,
            "publish_time": self.publish_time,
            "play_count": self.play_count,
            "like_count": self.like_count,
            "coin_count": self.coin_count,
            "favorite_count": self.favorite_count,
            "share_count": self.share_count
        }

    def get_url(self) -> str:
        """Get the video URL."""
        if self.bvid:
            return f"https://www.bilibili.com/video/{self.bvid}"
        elif self.aid:
            return f"https://www.bilibili.com/video/av{self.aid}"
        return ""

    def get_publish_datetime(self) -> datetime | None:
        """Get publish time as datetime object."""
        if self.publish_time:
            return datetime.fromtimestamp(self.publish_time)
        return None


@dataclass
class UPMasterState:
    """State tracking for a single UP master."""
    mid: str
    last_check_time: int  # Unix timestamp
    last_video_bvid: str | None = None
    last_video_aid: int | None = None
    processed_videos: set[str] = field(default_factory=set)  # Set of bvids

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UPMasterState:
        return cls(
            mid=str(data.get("mid", "")),
            last_check_time=int(data.get("last_check_time", 0)),
            last_video_bvid=data.get("last_video_bvid"),
            last_video_aid=data.get("last_video_aid"),
            processed_videos=set(data.get("processed_videos", []))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mid": self.mid,
            "last_check_time": self.last_check_time,
            "last_video_bvid": self.last_video_bvid,
            "last_video_aid": self.last_video_aid,
            "processed_videos": list(self.processed_videos)
        }

    def mark_video_processed(self, bvid: str) -> None:
        """Mark a video as processed."""
        self.processed_videos.add(bvid)

    def is_video_processed(self, bvid: str) -> bool:
        """Check if a video has been processed."""
        return bvid in self.processed_videos


@dataclass
class MonitorState:
    """Overall monitoring state for all UP masters."""
    up_masters: dict[str, UPMasterState] = field(default_factory=dict)
    last_save_time: int = 0
    content_history: list[dict[str, Any]] = field(default_factory=list)  # Searchable content history

    @classmethod
    def load_from_file(cls, file_path: Path) -> MonitorState:
        """Load state from JSON file."""
        if not file_path.exists():
            return cls()

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                state = cls()
                state.last_save_time = data.get("last_save_time", 0)
                state.content_history = data.get("content_history", [])
                for mid, up_data in data.get("up_masters", {}).items():
                    state.up_masters[mid] = UPMasterState.from_dict(up_data)
                return state
        except Exception:
            # If file is corrupted, return empty state
            return cls()

    def save_to_file(self, file_path: Path) -> None:
        """Save state to JSON file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "last_save_time": int(datetime.now().timestamp()),
            "up_masters": {
                mid: state.to_dict()
                for mid, state in self.up_masters.items()
            },
            "content_history": self.content_history
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_or_create_up_state(self, mid: str) -> UPMasterState:
        """Get or create state for an UP master."""
        if mid not in self.up_masters:
            self.up_masters[mid] = UPMasterState(
                mid=mid,
                last_check_time=0
            )
        return self.up_masters[mid]

    def add_content_to_history(self, content_item: dict[str, Any]) -> None:
        """Add a content item to searchable history."""
        self.content_history.append(content_item)

    def cleanup_old_history(self, max_items: int = 1000) -> None:
        """Remove old content history to prevent state file from growing too large."""
        if len(self.content_history) > max_items:
            # Keep only the most recent items
            self.content_history = self.content_history[-max_items:]


@dataclass(slots=True)
class MonitorReport:
    """Report of new videos from monitored UP masters."""
    up_master_name: str
    up_master_mid: str
    new_videos: list[VideoInfo] = field(default_factory=list)
    ai_summary: str | None = None
    check_time: datetime = field(default_factory=datetime.now)

    def has_new_videos(self) -> bool:
        """Check if there are any new videos."""
        return len(self.new_videos) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "up_master_name": self.up_master_name,
            "up_master_mid": self.up_master_mid,
            "new_videos": [v.to_dict() for v in self.new_videos],
            "ai_summary": self.ai_summary,
            "check_time": self.check_time.isoformat()
        }

