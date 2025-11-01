"""
Report export and archive service.

Provides functionality to export reports in multiple formats (JSON, Markdown, HTML)
and manage report archives for historical analysis.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from dataclasses import dataclass, field

from models.report import DailyReport


logger = logging.getLogger(__name__)


@dataclass
class ExportConfig:
    """Configuration for report export."""
    
    format: Literal["json", "markdown", "html"] = "json"
    include_charts: bool = False
    include_metadata: bool = True
    pretty_print: bool = True
    output_dir: Path = field(default_factory=lambda: Path("data/exports"))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "format": self.format,
            "include_charts": self.include_charts,
            "include_metadata": self.include_metadata,
            "pretty_print": self.pretty_print,
            "output_dir": str(self.output_dir)
        }


@dataclass
class ExportResult:
    """Result of an export operation."""
    
    success: bool
    file_path: Path | None = None
    format: str | None = None
    size_bytes: int = 0
    error: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "file_path": str(self.file_path) if self.file_path else None,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "error": self.error
        }


class ReportExporter:
    """Export reports in multiple formats."""
    
    def __init__(self, config: ExportConfig | None = None):
        """
        Initialize report exporter.
        
        Args:
            config: Export configuration
        """
        self.config = config or ExportConfig()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_report(
        self,
        report: DailyReport,
        format: Literal["json", "markdown", "html"] | None = None,
        filename: str | None = None,
        charts: dict[str, str | bytes] | None = None
    ) -> ExportResult:
        """
        Export a daily report to file.
        
        Args:
            report: Daily report to export
            format: Export format (overrides config)
            filename: Custom filename (auto-generated if None)
            charts: Optional charts to include
            
        Returns:
            ExportResult with operation details
        """
        export_format = format or self.config.format
        
        try:
            # Generate filename if not provided
            if not filename:
                date_str = report.report_date.strftime("%Y%m%d")
                filename = f"report_{date_str}.{export_format}"
            
            file_path = self.config.output_dir / filename
            
            # Export based on format
            if export_format == "json":
                content = self._export_json(report, charts)
            elif export_format == "markdown":
                content = self._export_markdown(report, charts)
            elif export_format == "html":
                content = self._export_html(report, charts)
            else:
                return ExportResult(
                    success=False,
                    error=f"Unsupported format: {export_format}"
                )
            
            # Write to file
            if isinstance(content, str):
                file_path.write_text(content, encoding="utf-8")
            else:
                file_path.write_bytes(content)
            
            size_bytes = file_path.stat().st_size
            
            logger.info(f"Exported report to {file_path} ({size_bytes} bytes)")
            
            return ExportResult(
                success=True,
                file_path=file_path,
                format=export_format,
                size_bytes=size_bytes
            )
            
        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            return ExportResult(
                success=False,
                error=str(e)
            )
    
    def _export_json(
        self,
        report: DailyReport,
        charts: dict[str, str | bytes] | None = None
    ) -> str:
        """Export report as JSON."""
        data = report.to_dict()
        
        # Add metadata if enabled
        if self.config.include_metadata:
            data["export_metadata"] = {
                "exported_at": datetime.now().isoformat(),
                "format": "json",
                "version": "1.0"
            }
        
        # Add charts if provided and enabled
        if self.config.include_charts and charts:
            data["charts"] = {}
            for name, chart_data in charts.items():
                if isinstance(chart_data, bytes):
                    # Convert bytes to base64 for JSON
                    import base64
                    data["charts"][name] = base64.b64encode(chart_data).decode("utf-8")
                else:
                    data["charts"][name] = chart_data
        
        # Pretty print if enabled
        if self.config.pretty_print:
            return json.dumps(data, ensure_ascii=False, indent=2)
        else:
            return json.dumps(data, ensure_ascii=False)
    
    def _export_markdown(
        self,
        report: DailyReport,
        charts: dict[str, str | bytes] | None = None
    ) -> str:
        """Export report as Markdown."""
        lines = [
            f"# {report.title}",
            "",
            f"📅 **日期**: {report.report_date.strftime('%Y年%m月%d日')}",
            ""
        ]
        
        # Add metadata if enabled
        if self.config.include_metadata:
            lines.extend([
                "## 📋 报告信息",
                "",
                f"- 生成时间: {report.generation_time.strftime('%Y-%m-%d %H:%M:%S') if report.generation_time else 'N/A'}",
                f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                ""
            ])
        
        # Statistics
        lines.extend([
            "## 📊 统计信息",
            "",
            f"- 📝 总内容数: {report.total_items}",
            f"- 📺 B站视频: {report.bilibili_items}",
            f"- 📰 知乎内容: {report.zhihu_items}",
            f"- 📂 分类数: {len(report.sections)}",
            ""
        ])
        
        # Executive summary
        if report.executive_summary:
            lines.extend([
                "## 📋 执行摘要",
                "",
                report.executive_summary,
                ""
            ])
        
        # Trending topics
        if report.trending_topics:
            topics_str = " · ".join(f"`{topic}`" for topic in report.trending_topics)
            lines.extend([
                "## 🔥 热门话题",
                "",
                topics_str,
                ""
            ])
        
        # Content sections
        for section in report.sections:
            lines.extend([
                f"## {section.category.value}",
                ""
            ])
            
            if section.ai_summary:
                lines.extend([
                    f"**AI 总结**: {section.ai_summary}",
                    ""
                ])
            
            for idx, item in enumerate(section.items, 1):
                lines.append(f"### {idx}. {item.title}")
                
                if item.author:
                    lines.append(f"👤 **作者**: {item.author}")
                
                if item.published:
                    lines.append(f"📅 **发布**: {item.published.strftime('%Y-%m-%d %H:%M')}")
                
                lines.append(f"⭐ **重要度**: {item.importance_score:.2f}")
                lines.append(f"🔗 **链接**: {item.url}")
                
                if item.summary:
                    lines.extend(["", item.summary])
                
                lines.append("")
        
        # Charts note
        if self.config.include_charts and charts:
            lines.extend([
                "---",
                "",
                "## 📊 图表",
                "",
                f"本报告包含 {len(charts)} 个可视化图表。",
                "图表已保存为单独的文件。",
                ""
            ])
        
        return "\n".join(lines)
    
    def _export_html(
        self,
        report: DailyReport,
        charts: dict[str, str | bytes] | None = None
    ) -> str:
        """Export report as HTML."""
        # HTML template
        html_parts = [
            "<!DOCTYPE html>",
            "<html lang='zh-CN'>",
            "<head>",
            "    <meta charset='UTF-8'>",
            "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            f"    <title>{report.title}</title>",
            "    <style>",
            "        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }",
            "        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }",
            "        h2 { color: #34495e; margin-top: 30px; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; }",
            "        h3 { color: #7f8c8d; }",
            "        .metadata { background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }",
            "        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }",
            "        .stat-card { background: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 5px; text-align: center; }",
            "        .stat-value { font-size: 2em; font-weight: bold; color: #3498db; }",
            "        .stat-label { color: #7f8c8d; margin-top: 5px; }",
            "        .content-item { background: #f8f9fa; padding: 15px; margin: 15px 0; border-left: 4px solid #3498db; border-radius: 3px; }",
            "        .content-item h3 { margin-top: 0; }",
            "        .meta-info { color: #7f8c8d; font-size: 0.9em; margin: 5px 0; }",
            "        .summary { margin-top: 10px; padding: 10px; background: #fff; border-radius: 3px; }",
            "        .topics { display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0; }",
            "        .topic-tag { background: #3498db; color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9em; }",
            "        a { color: #3498db; text-decoration: none; }",
            "        a:hover { text-decoration: underline; }",
            "    </style>",
            "</head>",
            "<body>",
            f"    <h1>{report.title}</h1>",
        ]
        
        # Metadata
        if self.config.include_metadata:
            html_parts.extend([
                "    <div class='metadata'>",
                f"        <p>📅 <strong>报告日期</strong>: {report.report_date.strftime('%Y年%m月%d日')}</p>",
                f"        <p>🕐 <strong>生成时间</strong>: {report.generation_time.strftime('%Y-%m-%d %H:%M:%S') if report.generation_time else 'N/A'}</p>",
                f"        <p>📤 <strong>导出时间</strong>: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
                "    </div>",
            ])
        
        # Statistics
        html_parts.extend([
            "    <h2>📊 统计信息</h2>",
            "    <div class='stats'>",
            f"        <div class='stat-card'><div class='stat-value'>{report.total_items}</div><div class='stat-label'>总内容数</div></div>",
            f"        <div class='stat-card'><div class='stat-value'>{report.bilibili_items}</div><div class='stat-label'>B站视频</div></div>",
            f"        <div class='stat-card'><div class='stat-value'>{report.zhihu_items}</div><div class='stat-label'>知乎内容</div></div>",
            f"        <div class='stat-card'><div class='stat-value'>{len(report.sections)}</div><div class='stat-label'>分类数</div></div>",
            "    </div>",
        ])
        
        # Executive summary
        if report.executive_summary:
            html_parts.extend([
                "    <h2>📋 执行摘要</h2>",
                f"    <div class='summary'>{report.executive_summary}</div>",
            ])
        
        # Trending topics
        if report.trending_topics:
            html_parts.append("    <h2>🔥 热门话题</h2>")
            html_parts.append("    <div class='topics'>")
            for topic in report.trending_topics:
                html_parts.append(f"        <span class='topic-tag'>{topic}</span>")
            html_parts.append("    </div>")
        
        # Content sections
        for section in report.sections:
            html_parts.append(f"    <h2>{section.category.value}</h2>")
            
            if section.ai_summary:
                html_parts.append(f"    <p><strong>AI 总结</strong>: {section.ai_summary}</p>")
            
            for idx, item in enumerate(section.items, 1):
                html_parts.append("    <div class='content-item'>")
                html_parts.append(f"        <h3>{idx}. {item.title}</h3>")
                
                meta_parts = []
                if item.author:
                    meta_parts.append(f"👤 {item.author}")
                if item.published:
                    meta_parts.append(f"📅 {item.published.strftime('%Y-%m-%d %H:%M')}")
                meta_parts.append(f"⭐ {item.importance_score:.2f}")
                
                html_parts.append(f"        <p class='meta-info'>{' | '.join(meta_parts)}</p>")
                html_parts.append(f"        <p class='meta-info'>🔗 <a href='{item.url}' target='_blank'>{item.url}</a></p>")
                
                if item.summary:
                    html_parts.append(f"        <div class='summary'>{item.summary}</div>")
                
                html_parts.append("    </div>")
        
        html_parts.extend([
            "</body>",
            "</html>"
        ])
        
        return "\n".join(html_parts)

