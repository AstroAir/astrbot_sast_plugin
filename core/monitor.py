"""
Core monitoring logic for Bilibili UP masters.

Handles video fetching, comparison, and new video detection.
"""
from __future__ import annotations

import asyncio

from core.bilibili_api import fetch_archives, get_bilibili_description
from models.bilibili import VideoInfo, MonitorReport, UPMasterConfig
from core.state import StateManager


class BilibiliMonitor:
    """Monitor Bilibili UP masters for new videos."""

    def __init__(self, state_manager: StateManager):
        """Initialize monitor.
        
        Args:
            state_manager: State manager instance
        """
        self.state_manager = state_manager

    async def fetch_up_master_videos(
        self,
        mid: str,
        max_videos: int = 5
    ) -> list[VideoInfo]:
        """Fetch latest videos from an UP master.
        
        Args:
            mid: UP master's mid
            max_videos: Maximum number of videos to fetch
            
        Returns:
            List of VideoInfo objects
            
        Raises:
            Exception: If API request fails
        """
        try:
            archives = await fetch_archives(mid, ps=max_videos, orderby="pubdate")
            
            videos_data = archives.get("videos", [])
            if not isinstance(videos_data, list):
                return []
            
            videos = []
            for video_data in videos_data:
                if not isinstance(video_data, dict):
                    continue
                
                video = VideoInfo.from_api_response(video_data)
                videos.append(video)
            
            return videos
        except Exception as e:
            raise Exception(f"Failed to fetch videos for UP master {mid}: {e}") from e

    async def get_video_description(self, bvid: str) -> str:
        """Get detailed description for a video.
        
        Args:
            bvid: Video's bvid
            
        Returns:
            Video description text
        """
        try:
            desc_obj = await get_bilibili_description(bvid)
            return desc_obj.desc or ""
        except Exception:
            return ""

    def filter_new_videos(
        self,
        mid: str,
        videos: list[VideoInfo]
    ) -> list[VideoInfo]:
        """Filter out videos that have already been processed.
        
        Args:
            mid: UP master's mid
            videos: List of videos to filter
            
        Returns:
            List of new (unprocessed) videos
        """
        new_videos = []
        for video in videos:
            if video.bvid and self.state_manager.is_video_new(mid, video.bvid):
                new_videos.append(video)
        
        return new_videos

    async def check_up_master(
        self,
        up_config: UPMasterConfig,
        max_videos: int = 5,
        fetch_descriptions: bool = False
    ) -> MonitorReport:
        """Check an UP master for new videos.
        
        Args:
            up_config: UP master configuration
            max_videos: Maximum number of videos to check
            fetch_descriptions: Whether to fetch detailed descriptions
            
        Returns:
            MonitorReport with new videos
        """
        report = MonitorReport(
            up_master_name=up_config.name,
            up_master_mid=up_config.mid
        )

        try:
            # Fetch latest videos
            all_videos = await self.fetch_up_master_videos(
                up_config.mid,
                max_videos=max_videos
            )

            # Filter new videos
            new_videos = self.filter_new_videos(up_config.mid, all_videos)

            # Optionally fetch detailed descriptions
            if fetch_descriptions and new_videos:
                for video in new_videos:
                    if video.bvid and not video.desc:
                        desc = await self.get_video_description(video.bvid)
                        video.desc = desc
                        # Small delay to avoid rate limiting
                        await asyncio.sleep(0.5)

            report.new_videos = new_videos

            # Mark videos as processed
            if new_videos:
                bvids = [v.bvid for v in new_videos if v.bvid]
                self.state_manager.mark_videos_processed(up_config.mid, bvids)

        except Exception as e:
            # Log error but don't crash
            # The error will be handled by the caller
            raise Exception(f"Error checking UP master {up_config.name} ({up_config.mid}): {e}") from e

        return report

    async def check_multiple_up_masters(
        self,
        up_configs: list[UPMasterConfig],
        max_videos: int = 5,
        fetch_descriptions: bool = False,
        delay_between_checks: float = 1.0
    ) -> list[MonitorReport]:
        """Check multiple UP masters for new videos.
        
        Args:
            up_configs: List of UP master configurations
            max_videos: Maximum number of videos to check per UP master
            fetch_descriptions: Whether to fetch detailed descriptions
            delay_between_checks: Delay in seconds between checking each UP master
            
        Returns:
            List of MonitorReports
        """
        reports = []

        for up_config in up_configs:
            try:
                report = await self.check_up_master(
                    up_config,
                    max_videos=max_videos,
                    fetch_descriptions=fetch_descriptions
                )
                reports.append(report)

                # Delay between checks to avoid rate limiting
                if delay_between_checks > 0:
                    await asyncio.sleep(delay_between_checks)

            except Exception:
                # Continue checking other UP masters even if one fails
                # Create an empty report for failed checks
                reports.append(MonitorReport(
                    up_master_name=up_config.name,
                    up_master_mid=up_config.mid,
                    new_videos=[]
                ))

        return reports

    def get_reports_with_new_videos(
        self,
        reports: list[MonitorReport]
    ) -> list[MonitorReport]:
        """Filter reports to only those with new videos.
        
        Args:
            reports: List of all reports
            
        Returns:
            List of reports that have new videos
        """
        return [r for r in reports if r.has_new_videos()]

