"""
Chart generation utilities for daily reports.

Provides functions to generate various chart types using matplotlib:
- Category distribution (pie/bar charts)
- Content volume trends (line charts)
- Importance score distribution (histograms)
- Top sources (bar charts)
- Activity heatmaps (hour/day patterns)
"""
import asyncio
import io
import base64
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any
from collections import defaultdict, Counter

try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.figure import Figure
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from models.report import DailyReport, ContentCategory, ContentSource


class ChartConfig:
    """Configuration for chart generation."""
    
    def __init__(
        self,
        enabled: bool = True,
        output_format: str = "png",  # png, jpg, base64
        dpi: int = 100,
        figsize: tuple[int, int] = (10, 6),
        style: str = "seaborn-v0_8-darkgrid",
        color_scheme: str = "default",  # default, pastel, vibrant
        save_to_file: bool = False,
        output_dir: str = "data/charts"
    ):
        self.enabled = enabled
        self.output_format = output_format
        self.dpi = dpi
        self.figsize = figsize
        self.style = style
        self.color_scheme = color_scheme
        self.save_to_file = save_to_file
        self.output_dir = output_dir
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChartConfig":
        """Create ChartConfig from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            output_format=data.get("output_format", "png"),
            dpi=data.get("dpi", 100),
            figsize=tuple(data.get("figsize", [10, 6])),
            style=data.get("style", "seaborn-v0_8-darkgrid"),
            color_scheme=data.get("color_scheme", "default"),
            save_to_file=data.get("save_to_file", False),
            output_dir=data.get("output_dir", "data/charts")
        )


class ChartGenerator:
    """Generate charts for daily reports using matplotlib."""
    
    def __init__(self, config: ChartConfig | None = None):
        """Initialize chart generator."""
        self.config = config or ChartConfig()
        
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib is not installed. Install it with: pip install matplotlib")
        
        # Set matplotlib style
        if self.config.style in plt.style.available:
            plt.style.use(self.config.style)
        
        # Define color schemes
        self.color_schemes = {
            "default": plt.cm.Set3.colors,
            "pastel": plt.cm.Pastel1.colors,
            "vibrant": plt.cm.Set1.colors,
        }
    
    def _get_colors(self, n: int) -> list:
        """Get n colors from the configured color scheme."""
        scheme = self.color_schemes.get(self.config.color_scheme, self.color_schemes["default"])
        return [scheme[i % len(scheme)] for i in range(n)]
    
    async def _save_or_encode_figure(self, fig: Figure, filename: str) -> str | bytes:
        """Save figure to file or encode as base64."""
        def _save():
            buf = io.BytesIO()
            fig.savefig(buf, format=self.config.output_format, dpi=self.config.dpi, bbox_inches='tight')
            buf.seek(0)
            
            # Save to file if configured
            if self.config.save_to_file:
                output_path = Path(self.config.output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                filepath = output_path / f"{filename}.{self.config.output_format}"
                with open(filepath, 'wb') as f:
                    f.write(buf.getvalue())
                buf.seek(0)
            
            # Return base64 or bytes
            if self.config.output_format == "base64":
                return base64.b64encode(buf.getvalue()).decode('utf-8')
            else:
                return buf.getvalue()
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _save)
        plt.close(fig)
        return result
    
    async def generate_category_distribution_pie(self, report: DailyReport) -> str | bytes | None:
        """Generate pie chart showing content distribution by category."""
        if not report.sections:
            return None
        
        def _generate():
            fig, ax = plt.subplots(figsize=self.config.figsize)
            
            # Prepare data
            categories = [section.category.value for section in report.sections]
            counts = [len(section.items) for section in report.sections]
            
            # Create pie chart
            colors = self._get_colors(len(categories))
            wedges, texts, autotexts = ax.pie(
                counts,
                labels=categories,
                autopct='%1.1f%%',
                colors=colors,
                startangle=90
            )
            
            # Styling
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
            
            ax.set_title('Content Distribution by Category', fontsize=14, fontweight='bold')
            
            return fig
        
        loop = asyncio.get_event_loop()
        fig = await loop.run_in_executor(None, _generate)
        return await self._save_or_encode_figure(fig, f"category_distribution_{datetime.now().strftime('%Y%m%d')}")
    
    async def generate_category_distribution_bar(self, report: DailyReport) -> str | bytes | None:
        """Generate bar chart showing content distribution by category."""
        if not report.sections:
            return None
        
        def _generate():
            fig, ax = plt.subplots(figsize=self.config.figsize)
            
            # Prepare data
            categories = [section.category.value for section in report.sections]
            counts = [len(section.items) for section in report.sections]
            
            # Create bar chart
            colors = self._get_colors(len(categories))
            bars = ax.bar(categories, counts, color=colors, edgecolor='black', linewidth=1.2)
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{int(height)}',
                       ha='center', va='bottom', fontweight='bold')
            
            ax.set_xlabel('Category', fontsize=12, fontweight='bold')
            ax.set_ylabel('Number of Items', fontsize=12, fontweight='bold')
            ax.set_title('Content Distribution by Category', fontsize=14, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            
            # Rotate x-axis labels if needed
            plt.xticks(rotation=45, ha='right')
            
            return fig
        
        loop = asyncio.get_event_loop()
        fig = await loop.run_in_executor(None, _generate)
        return await self._save_or_encode_figure(fig, f"category_bar_{datetime.now().strftime('%Y%m%d')}")
    
    async def generate_importance_distribution(self, report: DailyReport) -> str | bytes | None:
        """Generate histogram showing importance score distribution."""
        # Collect all importance scores
        scores = []
        for section in report.sections:
            scores.extend([item.importance_score for item in section.items])
        
        if not scores:
            return None
        
        def _generate():
            fig, ax = plt.subplots(figsize=self.config.figsize)
            
            # Create histogram
            n, bins, patches = ax.hist(scores, bins=20, color='skyblue', edgecolor='black', alpha=0.7)
            
            # Color bars by importance level
            for i, patch in enumerate(patches):
                bin_center = (bins[i] + bins[i+1]) / 2
                if bin_center >= 0.7:
                    patch.set_facecolor('green')
                elif bin_center >= 0.4:
                    patch.set_facecolor('orange')
                else:
                    patch.set_facecolor('red')
            
            ax.set_xlabel('Importance Score', fontsize=12, fontweight='bold')
            ax.set_ylabel('Number of Items', fontsize=12, fontweight='bold')
            ax.set_title('Content Importance Distribution', fontsize=14, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            
            # Add average line
            avg_score = sum(scores) / len(scores)
            ax.axvline(avg_score, color='red', linestyle='--', linewidth=2, label=f'Average: {avg_score:.2f}')
            ax.legend()
            
            return fig
        
        loop = asyncio.get_event_loop()
        fig = await loop.run_in_executor(None, _generate)
        return await self._save_or_encode_figure(fig, f"importance_dist_{datetime.now().strftime('%Y%m%d')}")
    
    async def generate_top_sources(self, report: DailyReport, top_n: int = 10) -> str | bytes | None:
        """Generate bar chart showing top sources by content count."""
        # Count items by source
        source_counts = Counter()
        for section in report.sections:
            for item in section.items:
                source_counts[item.source.value] += 1
        
        if not source_counts:
            return None
        
        def _generate():
            fig, ax = plt.subplots(figsize=self.config.figsize)
            
            # Get top N sources
            top_sources = source_counts.most_common(top_n)
            sources = [s[0] for s in top_sources]
            counts = [s[1] for s in top_sources]
            
            # Create horizontal bar chart
            colors = self._get_colors(len(sources))
            bars = ax.barh(sources, counts, color=colors, edgecolor='black', linewidth=1.2)
            
            # Add value labels
            for bar in bars:
                width = bar.get_width()
                ax.text(width, bar.get_y() + bar.get_height()/2.,
                       f'{int(width)}',
                       ha='left', va='center', fontweight='bold', fontsize=10)
            
            ax.set_xlabel('Number of Items', fontsize=12, fontweight='bold')
            ax.set_ylabel('Source', fontsize=12, fontweight='bold')
            ax.set_title(f'Top {len(sources)} Content Sources', fontsize=14, fontweight='bold')
            ax.grid(axis='x', alpha=0.3)
            
            return fig
        
        loop = asyncio.get_event_loop()
        fig = await loop.run_in_executor(None, _generate)
        return await self._save_or_encode_figure(fig, f"top_sources_{datetime.now().strftime('%Y%m%d')}")


    async def generate_activity_heatmap(self, report: DailyReport) -> str | bytes | None:
        """Generate heatmap showing posting patterns by hour and day of week."""
        # Collect posting times
        posting_times = []
        for section in report.sections:
            for item in section.items:
                if item.published:
                    posting_times.append(item.published)

        if not posting_times:
            return None

        def _generate():
            fig, ax = plt.subplots(figsize=(12, 6))

            # Create 7x24 matrix (days x hours)
            heatmap_data = np.zeros((7, 24))

            # Fill matrix with posting counts
            for dt in posting_times:
                day_of_week = dt.weekday()  # 0=Monday, 6=Sunday
                hour = dt.hour
                heatmap_data[day_of_week][hour] += 1

            # Create heatmap
            im = ax.imshow(heatmap_data, cmap='YlOrRd', aspect='auto')

            # Set ticks and labels
            ax.set_xticks(np.arange(24))
            ax.set_yticks(np.arange(7))
            ax.set_xticklabels([f'{h:02d}:00' for h in range(24)])
            ax.set_yticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])

            # Rotate x-axis labels
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

            # Add colorbar
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label('Number of Posts', rotation=270, labelpad=20, fontweight='bold')

            # Add text annotations
            for i in range(7):
                for j in range(24):
                    count = int(heatmap_data[i, j])
                    if count > 0:
                        text = ax.text(j, i, count, ha="center", va="center",
                                     color="white" if count > heatmap_data.max()/2 else "black",
                                     fontsize=8, fontweight='bold')

            ax.set_title('Content Posting Activity Heatmap', fontsize=14, fontweight='bold')
            ax.set_xlabel('Hour of Day', fontsize=12, fontweight='bold')
            ax.set_ylabel('Day of Week', fontsize=12, fontweight='bold')

            return fig

        loop = asyncio.get_event_loop()
        fig = await loop.run_in_executor(None, _generate)
        return await self._save_or_encode_figure(fig, f"activity_heatmap_{datetime.now().strftime('%Y%m%d')}")

    async def generate_content_timeline(self, report: DailyReport) -> str | bytes | None:
        """Generate line chart showing content volume over time."""
        # Collect posting times
        posting_times = []
        for section in report.sections:
            for item in section.items:
                if item.published:
                    posting_times.append(item.published)

        if not posting_times:
            return None

        def _generate():
            fig, ax = plt.subplots(figsize=self.config.figsize)

            # Sort times
            posting_times.sort()

            # Group by hour
            hourly_counts = defaultdict(int)
            for dt in posting_times:
                hour_key = dt.replace(minute=0, second=0, microsecond=0)
                hourly_counts[hour_key] += 1

            # Prepare data for plotting
            hours = sorted(hourly_counts.keys())
            counts = [hourly_counts[h] for h in hours]

            # Create line chart
            ax.plot(hours, counts, marker='o', linewidth=2, markersize=6, color='steelblue')
            ax.fill_between(hours, counts, alpha=0.3, color='steelblue')

            # Format x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            plt.xticks(rotation=45, ha='right')

            ax.set_xlabel('Time', fontsize=12, fontweight='bold')
            ax.set_ylabel('Number of Posts', fontsize=12, fontweight='bold')
            ax.set_title('Content Volume Timeline', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)

            return fig

        loop = asyncio.get_event_loop()
        fig = await loop.run_in_executor(None, _generate)
        return await self._save_or_encode_figure(fig, f"content_timeline_{datetime.now().strftime('%Y%m%d')}")

    async def generate_all_charts(self, report: DailyReport) -> dict[str, str | bytes]:
        """Generate all available charts for the report."""
        charts = {}

        try:
            # Category distribution (bar chart preferred over pie for readability)
            chart = await self.generate_category_distribution_bar(report)
            if chart:
                charts['category_distribution'] = chart
        except Exception as e:
            print(f"Failed to generate category distribution chart: {e}")

        try:
            # Importance distribution
            chart = await self.generate_importance_distribution(report)
            if chart:
                charts['importance_distribution'] = chart
        except Exception as e:
            print(f"Failed to generate importance distribution chart: {e}")

        try:
            # Top sources
            chart = await self.generate_top_sources(report)
            if chart:
                charts['top_sources'] = chart
        except Exception as e:
            print(f"Failed to generate top sources chart: {e}")

        try:
            # Activity heatmap
            chart = await self.generate_activity_heatmap(report)
            if chart:
                charts['activity_heatmap'] = chart
        except Exception as e:
            print(f"Failed to generate activity heatmap: {e}")

        try:
            # Content timeline
            chart = await self.generate_content_timeline(report)
            if chart:
                charts['content_timeline'] = chart
        except Exception as e:
            print(f"Failed to generate content timeline: {e}")

        return charts


def is_available() -> bool:
    """Check if matplotlib is available."""
    return MATPLOTLIB_AVAILABLE

