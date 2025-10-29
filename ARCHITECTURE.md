# AstrBot SAST Plugin - Architecture Documentation

## Overview

This plugin provides comprehensive content monitoring and analysis tools for the AstrBot framework, including:
- **Bilibili Monitoring**: Video description fetching, link extraction, AI summarization, and UP master monitoring
- **Zhihu RSS Monitoring**: RSS feed subscription with Bilibili link extraction
- **Advanced Scheduling**: Cron-like scheduling with error recovery and task monitoring
- **AI Daily Reports**: Intelligent daily content aggregation with AI-powered summaries and trending analysis
- **Data Visualization**: Beautiful charts and graphs for daily reports (category distribution, importance scores, activity heatmaps, etc.)

## Architecture

The plugin follows a clean, modular architecture with clear separation of concerns:

```text
astrbot-plugin-sast/
├── main.py                      # Plugin entry point and command handlers
├── core/                        # Core business logic
│   ├── bilibili_api.py         # Bilibili API client
│   ├── monitor.py              # UP master monitoring logic
│   ├── state.py                # Bilibili state persistence
│   ├── zhihu_rss.py            # Zhihu RSS feed client
│   ├── zhihu_state.py          # Zhihu state persistence
│   └── scheduler.py            # Advanced task scheduling
├── models/                      # Data models
│   ├── bilibili.py             # Bilibili data structures
│   ├── zhihu.py                # Zhihu RSS data structures
│   └── report.py               # Daily report data structures
├── services/                    # High-level services
│   ├── ai_summarizer.py        # AI-powered video analysis
│   ├── formatter.py            # Bilibili Markdown formatting
│   ├── zhihu_formatter.py      # Zhihu Markdown formatting
│   ├── report_aggregator.py   # Content aggregation
│   └── daily_report.py         # AI daily report generation
└── utils/                       # Reusable utilities
    ├── command_utils.py        # Shared command processing
    ├── link_extractor.py       # Bilibili link extraction
    ├── chart_generator.py      # Chart and visualization generation
    ├── openrouter_client.py    # OpenRouter API client
    └── tavily_client.py        # Tavily Extract API client
```

## Module Descriptions

### Core Modules (`core/`)

#### `bilibili_api.py`
- **Purpose**: Bilibili API integration
- **Key Functions**:
  - `get_bilibili_description(identifier)`: Fetch video description by BV/AV ID
  - `fetch_archives(mid, ps, pn)`: Fetch user's video archives
  - `pick_latest_from_archives(archives)`: Extract latest video from archives
- **Dependencies**: httpx, models.bilibili

#### `monitor.py`
- **Purpose**: UP master monitoring and new video detection
- **Key Classes**:
  - `BilibiliMonitor`: Manages monitoring logic for multiple UP masters
- **Key Methods**:
  - `check_up_master(config, max_videos)`: Check single UP master for new videos
  - `check_multiple_up_masters(configs, max_videos)`: Batch check multiple UP masters
  - `get_reports_with_new_videos(reports)`: Filter reports with new content
- **Dependencies**: core.bilibili_api, core.state, models.bilibili

#### `state.py`

- **Purpose**: State persistence for tracking processed Bilibili videos
- **Key Classes**:
  - `StateManager`: Manages JSON-based state storage
- **Key Methods**:
  - `load_state()`: Load monitoring state from disk
  - `save_state(state)`: Persist state to disk
  - `is_video_new(mid, bvid)`: Check if video has been processed
  - `mark_videos_processed(mid, bvids)`: Mark videos as seen
- **Dependencies**: models.bilibili

#### `zhihu_rss.py`

- **Purpose**: Zhihu RSS feed client for fetching and parsing feeds
- **Key Classes**:
  - `ZhihuRSSClient`: Manages RSS feed fetching and parsing
- **Key Methods**:
  - `fetch_feed(feed_url)`: Fetch RSS feed content
  - `parse_feed_item(entry)`: Parse feed entry into ZhihuFeedItem
  - `check_feed(config, state)`: Check feed for new items
  - `check_multiple_feeds(configs, state)`: Batch check multiple feeds
- **Dependencies**: feedparser, httpx, models.zhihu, utils.link_extractor

#### `zhihu_state.py`

- **Purpose**: State persistence for tracking processed Zhihu RSS items
- **Key Classes**:
  - `ZhihuStateManager`: Manages Zhihu monitoring state
- **Key Methods**:
  - `load_state()`: Load state from file
  - `save_state()`: Save state to file
  - `is_item_new(feed_url, item_id)`: Check if item is new
  - `mark_items_processed(feed_url, item_ids)`: Mark items as processed
- **Dependencies**: models.zhihu

#### `scheduler.py`

- **Purpose**: Advanced task scheduling with cron support and error recovery
- **Key Classes**:
  - `SchedulerManager`: Manages scheduled tasks using APScheduler
  - `TaskConfig`: Configuration for scheduled tasks
  - `TaskStatus`: Status information for tasks
- **Key Features**:
  - Cron expression support (e.g., "0 9 * * *")
  - Interval-based scheduling (minutes/hours)
  - Error recovery with exponential backoff
  - Task monitoring and health checks
  - Fallback to simple interval scheduling if APScheduler unavailable
- **Dependencies**: apscheduler (optional)

### Models (`models/`)

#### `bilibili.py`

- **Purpose**: Data structures for Bilibili entities
- **Key Classes**:
  - `BilibiliDescription`: Video description data
  - `VideoInfo`: Video metadata and statistics
  - `UPMasterConfig`: UP master monitoring configuration
  - `UPMasterState`: Per-UP-master state tracking
  - `MonitorState`: Global monitoring state
  - `MonitorReport`: Monitoring check results
- **Features**: Serialization/deserialization, URL generation, datetime parsing

#### `zhihu.py`

- **Purpose**: Data structures for Zhihu RSS feeds
- **Key Classes**:
  - `ZhihuFeedItem`: Single RSS feed item with Bilibili link extraction
  - `ZhihuFeedConfig`: RSS feed configuration
  - `ZhihuFeedState`: Per-feed state tracking
  - `ZhihuMonitorState`: Global Zhihu monitoring state
  - `ZhihuMonitorReport`: Feed check results
- **Features**: Serialization/deserialization, datetime parsing, Bilibili link tracking

#### `report.py`

- **Purpose**: Data structures for AI-powered daily reports
- **Key Classes**:
  - `ContentSource`: Enum for content sources (Bilibili, Zhihu, Other)
  - `ContentCategory`: Enum for content categories (Technology, Entertainment, Education, News, Lifestyle, Other)
  - `ContentItem`: Unified content item from any source
  - `CategorySection`: Report section grouped by category
  - `DailyReportConfig`: Configuration for daily report generation
  - `DailyReport`: Complete daily report with aggregated content
- **Features**: Content categorization, importance scoring, AI summary integration

### Services (`services/`)

#### `ai_summarizer.py`
- **Purpose**: AI-powered video content analysis
- **Key Classes**:
  - `AISummarizer`: Orchestrates AI summarization workflow
- **Key Methods**:
  - `summarize_report(report)`: Generate AI summary for single report
  - `summarize_multiple_reports(reports)`: Batch summarize multiple reports
- **Dependencies**: utils.openrouter_client, models.bilibili

#### `formatter.py`

- **Purpose**: Markdown report generation for Bilibili content
- **Key Classes**:
  - `MarkdownFormatter`: Formats monitor reports as Markdown
- **Formatting Styles**:
  - `simple`: Minimal format with titles and links
  - `detailed`: Full format with descriptions and statistics
  - `compact`: Table-based format for space efficiency
- **Key Methods**:
  - `format_report(report)`: Format single report
  - `format_multiple_reports(reports, title)`: Format batch report
  - `format_summary_only(report)`: Format only AI summary
- **Dependencies**: models.bilibili

#### `zhihu_formatter.py`

- **Purpose**: Markdown report generation for Zhihu RSS content
- **Key Classes**:
  - `ZhihuFormatter`: Formats Zhihu monitor reports as Markdown
- **Formatting Styles**:
  - `simple`: Minimal format with titles and links
  - `detailed`: Full format with summaries and Bilibili links
  - `compact`: Table-based format
- **Key Methods**:
  - `format_report(report)`: Format single report
  - `format_multiple_reports(reports, title)`: Format batch report
  - `format_bilibili_links_only(reports)`: Format only Bilibili links from Zhihu content
- **Dependencies**: models.zhihu

#### `report_aggregator.py`

- **Purpose**: Content aggregation from multiple sources for daily reports
- **Key Classes**:
  - `ReportAggregator`: Aggregates content from Bilibili and Zhihu
- **Key Methods**:
  - `collect_bilibili_content(reports, since)`: Collect Bilibili content
  - `collect_zhihu_content(reports, since)`: Collect Zhihu content
  - `aggregate_all(...)`: Aggregate all content into daily report
- **Features**:
  - Automatic content categorization
  - Importance scoring
  - Filtering by time and importance
- **Dependencies**: models.bilibili, models.zhihu, models.report

#### `daily_report.py`

- **Purpose**: AI-powered daily report generation
- **Key Classes**:
  - `DailyReportGenerator`: Generates comprehensive daily reports
- **Key Methods**:
  - `generate_section_summary(section)`: Generate AI summary for category section
  - `generate_executive_summary(report)`: Generate executive summary
  - `extract_trending_topics(report)`: Extract trending topics
  - `enhance_report(report, config)`: Enhance report with AI content
  - `format_markdown(report, config)`: Format as Markdown
  - `format_text(report, config)`: Format as plain text
  - `generate(report, config)`: Generate complete formatted report
- **Features**:
  - AI-powered summaries and insights
  - Trending topic extraction
  - Multiple output formats (Markdown, Text, HTML)
  - Customizable templates
- **Dependencies**: models.report, utils.openrouter_client

### Utilities (`utils/`)

#### `command_utils.py`
- **Purpose**: Shared command processing logic (eliminates code duplication)
- **Key Functions**:
  - `parse_command_flags(argv)`: Parse command-line flags
  - `extract_and_summarize_urls(description, flags, ...)`: Unified URL extraction and AI summarization workflow
- **Dependencies**: utils.tavily_client, utils.openrouter_client

#### `openrouter_client.py`
- **Purpose**: OpenRouter API integration for AI summarization
- **Key Functions**:
  - `summarize_batch(pairs, options)`: Batch summarize URL contents
  - `build_summary_prompt(url, content, language)`: Generate summarization prompt
- **Dependencies**: httpx

#### `tavily_client.py`

- **Purpose**: Tavily Extract API integration for web content extraction
- **Key Functions**:
  - `extract_urls(text)`: Extract URLs from text
  - `tavily_extract(urls, options)`: Extract content from URLs
- **Dependencies**: httpx

#### `link_extractor.py`

- **Purpose**: Bilibili video link extraction and normalization
- **Key Functions**:
  - `extract_bilibili_links(text)`: Extract all Bilibili video URLs from text
  - `normalize_bilibili_url(url)`: Convert to standard format
  - `extract_video_id(url)`: Get BV/AV ID from URL
  - `is_bilibili_url(url)`: Validate if URL is Bilibili video
  - `deduplicate_links(links)`: Remove duplicates based on video ID
- **Supported URL Formats**:
  - Standard: `https://www.bilibili.com/video/BV...`
  - AV format: `https://www.bilibili.com/video/av...`
  - Short links: `https://b23.tv/...`
  - Mobile: `https://m.bilibili.com/video/BV...`
- **Dependencies**: re (regex)

#### `chart_generator.py`

- **Purpose**: Generate visualizations and charts for daily reports
- **Key Classes**:
  - `ChartConfig`: Configuration for chart generation (format, DPI, size, style, colors)
  - `ChartGenerator`: Main chart generation class using matplotlib
- **Key Methods**:
  - `generate_category_distribution_pie(report)`: Pie chart of content by category
  - `generate_category_distribution_bar(report)`: Bar chart of content by category
  - `generate_importance_distribution(report)`: Histogram of importance scores
  - `generate_top_sources(report, top_n)`: Bar chart of top content sources
  - `generate_activity_heatmap(report)`: 7x24 heatmap of posting patterns
  - `generate_content_timeline(report)`: Line chart of content volume over time
  - `generate_all_charts(report)`: Generate all available charts
- **Output Formats**:
  - PNG/JPG: Image files (can be saved to disk or returned as bytes)
  - Base64: Encoded strings for embedding in markdown/HTML
- **Features**:
  - Async execution (runs in thread pool to avoid blocking)
  - Configurable styles (seaborn, ggplot, bmh, etc.)
  - Multiple color schemes (default, pastel, vibrant)
  - Automatic chart saving (optional)
  - Graceful fallback if matplotlib not installed
- **Dependencies**: matplotlib, numpy

## Plugin Entry Point (`main.py`)

### Class: `BiliToolsPlugin`

**Inherits**: `Star` (AstrBot plugin base class)

**Initialization**:
- Loads configuration from AstrBot context
- Initializes state manager and monitor
- Sets up AI summarizer (if enabled)
- Configures Markdown formatter
- Starts background monitoring task (if enabled)

### Commands

#### `/bili_desc <bvid|aid> [flags]`
- **Purpose**: Fetch video description and optionally extract/summarize links
- **Flags**:
  - `--extract`: Extract URLs from description
  - `--max N`: Maximum URLs to process (default: 3)
  - `--depth basic|advanced`: Tavily extraction depth
  - `--format markdown|text`: Tavily output format
  - `--summarize`: Generate AI summaries of extracted content
- **Implementation**: Uses `extract_and_summarize_urls()` utility to eliminate code duplication

#### `/bili_latest <mid> [flags]`
- **Purpose**: Fetch latest video from user and optionally extract/summarize links
- **Flags**: Same as `/bili_desc`
- **Implementation**: Uses `extract_and_summarize_urls()` utility to eliminate code duplication

#### `/bili_monitor`

- **Purpose**: Manually trigger monitoring check for configured UP masters
- **Behavior**:
  - Checks all configured UP masters for new videos
  - Generates AI summaries (if enabled)
  - Formats and returns Markdown report

#### `/zhihu_check` (Planned)

- **Purpose**: Manually trigger Zhihu RSS feed check
- **Behavior**:
  - Checks all configured Zhihu RSS feeds for new items
  - Extracts Bilibili links from content (if enabled)
  - Formats and returns Markdown report

#### `/daily_report` (Planned)

- **Purpose**: Manually generate daily content report
- **Behavior**:
  - Aggregates content from all sources (Bilibili, Zhihu)
  - Categorizes content by topic
  - Generates AI summaries and trending analysis
  - Returns comprehensive daily report

### Background Monitoring

**Bilibili Monitoring**:

- Runs periodically based on `check_interval` or `bilibili_cron` configuration
- Checks all configured UP masters for new videos
- Generates AI summaries (if enabled)
- Sends formatted reports to configured target groups

**Zhihu RSS Monitoring**:

- Runs periodically based on `zhihu_check_interval` or `zhihu_cron` configuration
- Checks all configured RSS feeds for new items
- Extracts Bilibili links from content
- Sends formatted reports to configured target groups

**Daily Report Generation**:

- Runs daily at configured time (`daily_report_time`)
- Aggregates content from all sources
- Generates AI-powered comprehensive report
- Sends to configured target groups

**Scheduler**:

- Uses APScheduler for advanced scheduling (if available)
- Supports cron expressions for flexible scheduling
- Implements error recovery with exponential backoff
- Monitors task health and status
- Falls back to simple interval-based scheduling if APScheduler unavailable

## Configuration

See `_conf_schema.json` for the complete configuration schema. Key settings:

### Bilibili Monitoring

- `enabled`: Enable/disable Bilibili background monitoring
- `check_interval`: Monitoring interval in minutes (minimum: 5)
- `bilibili_cron`: Cron expression for advanced scheduling (optional)
- `up_masters`: List of UP masters to monitor (mid, name)
- `max_videos_per_check`: Maximum videos to fetch per check
- `include_video_stats`: Include view/like counts in reports

### Zhihu RSS Monitoring

- `zhihu_feeds`: List of RSS feeds to monitor (feed_url, name, enabled, check_bilibili_links)
- `zhihu_check_interval`: Check interval in minutes (minimum: 30)
- `zhihu_cron`: Cron expression for advanced scheduling (optional)

### AI Features

- `ai_summary_enabled`: Enable/disable AI summarization
- `openrouter_api_key`: OpenRouter API key for AI features
- `openrouter_model`: AI model to use (default: minimax/minimax-m2:free)
- `ai_prompt_template`: Custom AI prompt template

### Daily Reports

- `daily_report_enabled`: Enable/disable daily report generation
- `daily_report_time`: Time to generate report (HH:MM format)
- `daily_report_categorize`: Enable content categorization
- `daily_report_ai_summary`: Enable AI summaries in reports
- `daily_report_min_importance`: Minimum importance score (0.0-1.0)
- `daily_report_max_items`: Maximum items per category

### Chart Visualization

- `chart_enabled`: Enable/disable chart generation (requires matplotlib)
- `chart_output_format`: Output format (png/jpg/base64)
- `chart_dpi`: Chart resolution/DPI (default: 100)
- `chart_figsize`: Chart dimensions in inches [width, height] (default: [10, 6])
- `chart_style`: Matplotlib style (seaborn-v0_8-darkgrid, ggplot, bmh, etc.)
- `chart_color_scheme`: Color scheme (default/pastel/vibrant)
- `chart_save_to_file`: Save charts to local files
- `chart_output_dir`: Directory for saved charts (default: data/charts)

**Available Chart Types**:
- Category distribution (bar chart)
- Importance score distribution (histogram)
- Top content sources (horizontal bar chart)
- Activity heatmap (7 days × 24 hours)
- Content timeline (line chart)

### Scheduling

- `use_advanced_scheduler`: Use APScheduler for advanced scheduling
- Supports cron expressions for flexible scheduling
- Automatic fallback to simple interval scheduling

### Output and Delivery

- `markdown_style`: Report formatting style (simple/detailed/compact)
- `target_groups`: Message delivery targets
- `batch_send_delay`: Delay between messages (seconds)
- `send_summary_only`: Send only AI summaries (no raw data)

## Design Principles

### 1. Separation of Concerns
- **Core**: Business logic and external API integration
- **Models**: Data structures and serialization
- **Services**: High-level orchestration
- **Utils**: Reusable, stateless utilities

### 2. Code Reusability
- Shared command processing logic in `utils/command_utils.py`
- Eliminates ~100 lines of duplicated code between `/bili_desc` and `/bili_latest`
- Consistent API client patterns across `tavily_client.py` and `openrouter_client.py`

### 3. Maintainability
- Clear module boundaries
- Comprehensive docstrings
- Type hints throughout
- Consistent error handling

### 4. AstrBot Compatibility
- Preserves required plugin structure (Star class, @register decorator)
- Uses async/await patterns with yield for passive responses
- Maintains backward compatibility with existing configurations

## API Dependencies

### External APIs

1. **UAPI (uapis.cn)**: Bilibili video information and user archives
2. **Tavily Extract API**: Web content extraction from URLs
3. **OpenRouter API**: AI summarization using minimax/minimax-m2:free model
4. **RSS Feeds**: Zhihu and other RSS/Atom feeds via feedparser

### Python Libraries

- **httpx**: Async HTTP client for all API calls
- **feedparser**: Universal RSS/Atom feed parser
- **apscheduler**: Advanced task scheduling (optional, with fallback)
- **matplotlib**: Chart and visualization generation (optional, with graceful fallback)
- **numpy**: Numerical operations for chart generation (dependency of matplotlib)
- **aiofiles**: Async file I/O
- **beautifulsoup4**: HTML parsing

### Environment Variables

- `TAVILY_API_KEY`: Tavily API authentication
- `OPENROUTER_API_KEY`: OpenRouter API authentication

## State Management

### Bilibili State

**File**: `data/bili_monitor_state.json`

**Structure**:

```json
{
  "up_masters": {
    "<mid>": {
      "mid": "<mid>",
      "name": "<name>",
      "processed_videos": ["<bvid1>", "<bvid2>", ...],
      "last_check_time": "<ISO 8601 timestamp>"
    }
  }
}
```

**Purpose**: Track processed Bilibili videos to avoid duplicate notifications

### Zhihu State

**File**: `data/zhihu_monitor_state.json`

**Structure**:

```json
{
  "feeds": {
    "<feed_url>": {
      "feed_url": "<feed_url>",
      "name": "<feed_name>",
      "processed_items": ["<guid1>", "<guid2>", ...],
      "last_check_time": "<ISO 8601 timestamp>",
      "last_error": null,
      "error_count": 0
    }
  }
}
```

**Purpose**: Track processed Zhihu RSS items to avoid duplicate notifications

## Implemented Features (v2.0)

### Phase 1: Core Refactoring (Completed)

- ✅ Modular architecture with clear separation of concerns
- ✅ Eliminated ~100 lines of code duplication
- ✅ Comprehensive documentation
- ✅ Zero diagnostic errors

### Phase 2: Zhihu RSS Support (Completed)

- ✅ RSS feed client with feedparser integration
- ✅ Bilibili link extraction from Zhihu content
- ✅ Separate state management for Zhihu feeds
- ✅ Markdown formatting for Zhihu reports

### Phase 3: Enhanced Scheduling (Completed)

- ✅ APScheduler integration with cron support
- ✅ Error recovery with exponential backoff
- ✅ Task monitoring and health checks
- ✅ Fallback to simple interval scheduling

### Phase 4: AI Daily Reports (Completed)

- ✅ Content aggregation from multiple sources
- ✅ Automatic content categorization
- ✅ Importance scoring
- ✅ AI-powered summaries and trending analysis
- ✅ Multiple output formats (Markdown, Text)

### Phase 5: Configuration and Integration (Completed)

- ✅ Extended configuration schema
- ✅ Comprehensive config examples
- ✅ Backward compatibility maintained

## Future Enhancements

Potential improvements for future versions:

1. **Command Integration**: Implement `/zhihu_check` and `/daily_report` commands in main.py
2. **Scheduler Integration**: Replace simple monitoring with scheduler-based approach
3. **Caching**: Add response caching for Bilibili and RSS API calls
4. **Rate Limiting**: Implement rate limiting for external API calls
5. **Testing**: Add unit tests for all modules
6. **Metrics**: Add monitoring metrics for API call success/failure rates
7. **HTML Output**: Add HTML formatting for daily reports
8. **Email Delivery**: Add email delivery option for daily reports
9. **Web Dashboard**: Add web interface for monitoring and configuration
10. **Multi-language Support**: Add i18n support for reports

## Migration Notes

### Phase 1 Refactoring (v1.0 → v2.0)

The refactoring consolidated the following old modules:

- `tools/bilibili_desc.py` → `core/bilibili_api.py`
- `tools/bili_monitor_models.py` → `models/bilibili.py`
- `tools/bili_monitor_state.py` → `core/state.py`
- `tools/bili_monitor_core.py` → `core/monitor.py`
- `tools/bili_monitor_ai.py` → `services/ai_summarizer.py`
- `tools/bili_monitor_markdown.py` → `services/formatter.py`
- `tools/tavily_extract.py` → `utils/tavily_client.py`
- `tools/openrouter_summarize.py` → `utils/openrouter_client.py`

### Phase 2 Enhancements (v2.0)

New modules added:

- `models/zhihu.py`: Zhihu RSS data models
- `models/report.py`: Daily report data models
- `core/zhihu_rss.py`: Zhihu RSS client
- `core/zhihu_state.py`: Zhihu state management
- `core/scheduler.py`: Advanced task scheduling
- `services/zhihu_formatter.py`: Zhihu report formatting
- `services/report_aggregator.py`: Content aggregation
- `services/daily_report.py`: AI daily report generation
- `utils/link_extractor.py`: Bilibili link extraction

### Backward Compatibility

- ✅ Configuration schema extended (not breaking)
- ✅ All existing commands work identically
- ✅ Bilibili state file format preserved
- ✅ Existing configurations continue to work
- ✅ New features are opt-in via configuration

