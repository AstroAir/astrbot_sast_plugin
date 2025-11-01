"""
Report archive management service.

Provides functionality to archive, retrieve, and manage historical reports
for long-term storage and analysis.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from models.report import DailyReport


logger = logging.getLogger(__name__)


@dataclass
class ArchiveMetadata:
    """Metadata for an archived report."""
    
    archive_id: str
    report_date: datetime
    archived_at: datetime
    file_path: Path
    file_size: int
    total_items: int
    bilibili_items: int
    zhihu_items: int
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "archive_id": self.archive_id,
            "report_date": self.report_date.isoformat(),
            "archived_at": self.archived_at.isoformat(),
            "file_path": str(self.file_path),
            "file_size": self.file_size,
            "total_items": self.total_items,
            "bilibili_items": self.bilibili_items,
            "zhihu_items": self.zhihu_items
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchiveMetadata:
        """Create from dictionary."""
        return cls(
            archive_id=data["archive_id"],
            report_date=datetime.fromisoformat(data["report_date"]),
            archived_at=datetime.fromisoformat(data["archived_at"]),
            file_path=Path(data["file_path"]),
            file_size=data["file_size"],
            total_items=data["total_items"],
            bilibili_items=data["bilibili_items"],
            zhihu_items=data["zhihu_items"]
        )


@dataclass
class ArchiveIndex:
    """Index of all archived reports."""
    
    archives: list[ArchiveMetadata] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "archives": [a.to_dict() for a in self.archives],
            "last_updated": self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchiveIndex:
        """Create from dictionary."""
        return cls(
            archives=[ArchiveMetadata.from_dict(a) for a in data.get("archives", [])],
            last_updated=datetime.fromisoformat(data.get("last_updated", datetime.now().isoformat()))
        )


class ArchiveManager:
    """Manage report archives."""
    
    def __init__(self, archive_dir: Path | None = None):
        """
        Initialize archive manager.
        
        Args:
            archive_dir: Directory for storing archives
        """
        self.archive_dir = archive_dir or Path("data/archives")
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_file = self.archive_dir / "index.json"
        self.index = self._load_index()
    
    def _load_index(self) -> ArchiveIndex:
        """Load archive index from file."""
        if not self.index_file.exists():
            return ArchiveIndex()
        
        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return ArchiveIndex.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load archive index: {e}")
            return ArchiveIndex()
    
    def _save_index(self):
        """Save archive index to file."""
        try:
            self.index.last_updated = datetime.now()
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.index.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save archive index: {e}")
    
    def archive_report(self, report: DailyReport) -> ArchiveMetadata | None:
        """
        Archive a daily report.
        
        Args:
            report: Daily report to archive
            
        Returns:
            ArchiveMetadata if successful, None otherwise
        """
        try:
            # Generate archive ID
            archive_id = report.report_date.strftime("%Y%m%d")
            
            # Check if already archived
            existing = self.get_archive(archive_id)
            if existing:
                logger.warning(f"Report for {archive_id} already archived")
                return existing
            
            # Create archive file
            filename = f"report_{archive_id}.json"
            file_path = self.archive_dir / filename
            
            # Save report
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
            
            # Create metadata
            metadata = ArchiveMetadata(
                archive_id=archive_id,
                report_date=report.report_date,
                archived_at=datetime.now(),
                file_path=file_path,
                file_size=file_path.stat().st_size,
                total_items=report.total_items,
                bilibili_items=report.bilibili_items,
                zhihu_items=report.zhihu_items
            )
            
            # Add to index
            self.index.archives.append(metadata)
            self._save_index()
            
            logger.info(f"Archived report {archive_id} ({metadata.file_size} bytes)")
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to archive report: {e}", exc_info=True)
            return None
    
    def get_archive(self, archive_id: str) -> ArchiveMetadata | None:
        """
        Get archive metadata by ID.
        
        Args:
            archive_id: Archive ID
            
        Returns:
            ArchiveMetadata if found, None otherwise
        """
        for archive in self.index.archives:
            if archive.archive_id == archive_id:
                return archive
        return None
    
    def load_report(self, archive_id: str) -> DailyReport | None:
        """
        Load a report from archive.
        
        Args:
            archive_id: Archive ID
            
        Returns:
            DailyReport if found, None otherwise
        """
        metadata = self.get_archive(archive_id)
        if not metadata:
            logger.warning(f"Archive {archive_id} not found")
            return None
        
        try:
            with open(metadata.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return DailyReport.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load report from archive: {e}")
            return None
    
    def list_archives(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int | None = None
    ) -> list[ArchiveMetadata]:
        """
        List archived reports.
        
        Args:
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of results
            
        Returns:
            List of archive metadata
        """
        archives = self.index.archives
        
        # Filter by date range
        if start_date:
            archives = [a for a in archives if a.report_date >= start_date]
        if end_date:
            archives = [a for a in archives if a.report_date <= end_date]
        
        # Sort by date (newest first)
        archives = sorted(archives, key=lambda a: a.report_date, reverse=True)
        
        # Apply limit
        if limit:
            archives = archives[:limit]
        
        return archives
    
    def delete_archive(self, archive_id: str) -> bool:
        """
        Delete an archived report.
        
        Args:
            archive_id: Archive ID
            
        Returns:
            True if deleted, False otherwise
        """
        metadata = self.get_archive(archive_id)
        if not metadata:
            logger.warning(f"Archive {archive_id} not found")
            return False
        
        try:
            # Delete file
            if metadata.file_path.exists():
                metadata.file_path.unlink()
            
            # Remove from index
            self.index.archives = [a for a in self.index.archives if a.archive_id != archive_id]
            self._save_index()
            
            logger.info(f"Deleted archive {archive_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete archive: {e}")
            return False
    
    def cleanup_old_archives(self, days: int = 90) -> int:
        """
        Delete archives older than specified days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of archives deleted
        """
        cutoff = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for archive in list(self.index.archives):
            if archive.report_date < cutoff:
                if self.delete_archive(archive.archive_id):
                    deleted_count += 1
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old archives (older than {days} days)")
        
        return deleted_count
    
    def get_statistics(self) -> dict[str, Any]:
        """
        Get archive statistics.
        
        Returns:
            Dictionary with statistics
        """
        if not self.index.archives:
            return {
                "total_archives": 0,
                "total_size_bytes": 0,
                "total_items": 0,
                "date_range": None
            }
        
        total_size = sum(a.file_size for a in self.index.archives)
        total_items = sum(a.total_items for a in self.index.archives)
        
        dates = [a.report_date for a in self.index.archives]
        date_range = {
            "earliest": min(dates).strftime("%Y-%m-%d"),
            "latest": max(dates).strftime("%Y-%m-%d")
        }
        
        return {
            "total_archives": len(self.index.archives),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "total_items": total_items,
            "date_range": date_range
        }

