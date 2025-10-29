# AstrBot SAST Plugin - Content Monitoring & Analysis

A comprehensive content monitoring and analysis plugin for AstrBot, providing Bilibili video tools, Zhihu RSS monitoring, advanced scheduling, and AI-powered daily reports.

## ✨ Features

### 📺 Bilibili Monitoring

- **Video Description Fetching**: Get video descriptions by BV/AV ID
- **Latest Video Tracking**: Fetch latest video from any UP master
- **Link Extraction**: Extract and analyze URLs from video descriptions
- **AI Summarization**: AI-powered video content analysis
- **UP Master Monitoring**: Automatic monitoring with new video detection
- **Rich Reports**: Markdown reports with statistics and AI summaries

### 📰 Zhihu RSS Monitoring

- **RSS Feed Subscription**: Monitor multiple Zhihu RSS feeds
- **Bilibili Link Extraction**: Automatically extract Bilibili video links from Zhihu content
- **Content Tracking**: Avoid duplicate notifications with state management
- **Flexible Formatting**: Multiple report styles (simple, detailed, compact)

### ⏰ Advanced Scheduling

- **Cron Support**: Use cron expressions for flexible scheduling (e.g., "0 9,12,18 * * *")
- **Multiple Tasks**: Independent schedules for Bilibili and Zhihu monitoring
- **Error Recovery**: Exponential backoff and circuit breaker patterns
- **Task Monitoring**: Health checks and status reporting
- **Fallback Mode**: Simple interval scheduling if APScheduler unavailable

### 📊 AI Daily Reports

- **Content Aggregation**: Collect content from all sources (Bilibili, Zhihu)
- **Smart Categorization**: Automatic categorization by topic (Technology, Entertainment, Education, News, Lifestyle)
- **Importance Scoring**: Intelligent content ranking and filtering
- **AI Summaries**: AI-powered executive summaries and trending analysis
- **Multiple Formats**: Markdown, plain text, and HTML output (planned)
- **Customizable**: Configurable importance thresholds and item limits

### 📈 Data Visualization

- **Beautiful Charts**: Automatically generate charts for daily reports using matplotlib
- **Multiple Chart Types**:
  - Category distribution (bar chart)
  - Importance score distribution (histogram)
  - Top content sources (horizontal bar chart)
  - Activity heatmap (7 days × 24 hours posting patterns)
  - Content timeline (line chart showing volume over time)
- **Flexible Output**: PNG, JPG, or base64-encoded images
- **Customizable Styling**: Multiple color schemes and matplotlib styles
- **Optional**: Gracefully disabled if matplotlib not installed

## Installation

1. Install the plugin in your AstrBot plugins directory
2. Configure the plugin using `_conf_schema.json`
3. Set up API keys (optional, for advanced features):
   - `TAVILY_API_KEY` for link extraction
   - `OPENROUTER_API_KEY` for AI summarization

## Commands

### `/bili_desc <bvid|aid> [flags]`

Get video description and optionally extract/summarize links.

**Flags:**
- `--extract`: Extract URLs from description
- `--max N`: Maximum URLs to process (default: 3)
- `--depth basic|advanced`: Tavily extraction depth
- `--format markdown|text`: Tavily output format
- `--summarize`: Generate AI summaries of extracted content

**Examples:**
```
/bili_desc BV1xx411c7mD
/bili_desc BV1xx411c7mD --extract --max 3
/bili_desc BV1xx411c7mD --extract --summarize
```

### `/bili_latest <mid> [flags]`

Get latest video from a Bilibili user and optionally extract/summarize links.

**Flags:** Same as `/bili_desc`

**Examples:**
```
/bili_latest 285286947
/bili_latest 285286947 --extract --max 2
/bili_latest 285286947 --extract --summarize
```

### `/bili_monitor`

Manually trigger monitoring check for configured UP masters.

**Example:**

```bash
/bili_monitor
```

### `/zhihu_check` ⚠️ (Not Yet Implemented)

Manually trigger Zhihu RSS feed check.

**Note**: The backend functionality is implemented, but the command handler needs to be added to main.py.

**Example:**

```bash
/zhihu_check
```

### `/daily_report` ⚠️ (Not Yet Implemented)

Manually generate daily content report.

**Note**: The backend functionality is implemented, but the command handler needs to be added to main.py. Additionally, the daily report generation needs to store recent reports in state for proper aggregation.

**Example:**

```bash
/daily_report
```

## Configuration

See `config_example.json` for a complete configuration example.

### Bilibili Monitoring

```json
{
  "enabled": true,
  "check_interval": 30,
  "bilibili_cron": "",
  "up_masters": [
    {
      "mid": "285286947",
      "name": "UP主名称"
    }
  ],
  "ai_summary_enabled": true,
  "markdown_style": "detailed"
}
```

### Zhihu RSS Monitoring

```json
{
  "zhihu_feeds": [
    {
      "feed_url": "https://rsshub.app/zhihu/hotlist",
      "name": "知乎热榜",
      "enabled": true,
      "check_bilibili_links": true
    }
  ],
  "zhihu_check_interval": 60,
  "zhihu_cron": ""
}
```

### Advanced Scheduling

```json
{
  "use_advanced_scheduler": true,
  "bilibili_cron": "0 9,12,18 * * *",
  "zhihu_cron": "0 */2 * * *"
}
```

**Cron Expression Examples:**

- `0 9,12,18 * * *` - Every day at 9 AM, 12 PM, and 6 PM
- `0 */2 * * *` - Every 2 hours
- `0 9 * * 1-5` - Weekdays at 9 AM

### Daily Reports

```json
{
  "daily_report_enabled": true,
  "daily_report_time": "09:00",
  "daily_report_categorize": true,
  "daily_report_ai_summary": true,
  "daily_report_min_importance": 0.3,
  "daily_report_max_items": 10
}
```

### Chart Visualization

```json
{
  "chart_enabled": true,
  "chart_output_format": "png",
  "chart_dpi": 100,
  "chart_figsize": [10, 6],
  "chart_style": "seaborn-v0_8-darkgrid",
  "chart_color_scheme": "default",
  "chart_save_to_file": false,
  "chart_output_dir": "data/charts"
}
```

**Chart Styles:**
- `seaborn-v0_8-darkgrid` - Dark grid (recommended)
- `ggplot` - R ggplot2 style
- `bmh` - Bayesian Methods for Hackers style
- `fivethirtyeight` - FiveThirtyEight news style

**Color Schemes:**
- `default` - Standard colors
- `pastel` - Soft, pastel colors
- `vibrant` - Bright, vibrant colors

### API Keys

```json
{
  "openrouter_api_key": "your-key-here",
  "openrouter_model": "minimax/minimax-m2:free"
}
```

Or set environment variables:

- `OPENROUTER_API_KEY`: For AI summarization
- `TAVILY_API_KEY`: For link extraction (optional)

## Architecture

The plugin follows a clean, modular architecture with four layers:

```text
astrbot-plugin-sast/
├── main.py                      # Plugin entry point
├── core/                        # Core business logic
│   ├── bilibili_api.py         # Bilibili API client
│   ├── monitor.py              # UP master monitoring
│   ├── state.py                # Bilibili state management
│   ├── zhihu_rss.py            # Zhihu RSS client
│   ├── zhihu_state.py          # Zhihu state management
│   └── scheduler.py            # Advanced scheduling
├── models/                      # Data models
│   ├── bilibili.py             # Bilibili data structures
│   ├── zhihu.py                # Zhihu RSS data structures
│   └── report.py               # Daily report data structures
├── services/                    # High-level services
│   ├── ai_summarizer.py        # AI-powered analysis
│   ├── formatter.py            # Bilibili formatting
│   ├── zhihu_formatter.py      # Zhihu formatting
│   ├── report_aggregator.py   # Content aggregation
│   └── daily_report.py         # AI daily reports
└── utils/                       # Reusable utilities
    ├── command_utils.py        # Command processing
    ├── link_extractor.py       # Bilibili link extraction
    ├── chart_generator.py      # Chart visualization
    ├── openrouter_client.py    # OpenRouter API
    └── tavily_client.py        # Tavily API
```

For detailed architecture documentation, see [ARCHITECTURE.md](ARCHITECTURE.md).

## API Dependencies

- **UAPI (uapis.cn)**: Bilibili video information and user archives
- **Tavily Extract API**: Web content extraction from URLs
- **OpenRouter API**: AI summarization using minimax/minimax-m2:free model
- **RSS Feeds**: Zhihu and other RSS/Atom feeds via feedparser

## Python Dependencies

- `httpx`: Async HTTP client
- `feedparser`: RSS/Atom feed parser
- `apscheduler`: Advanced task scheduling (optional)
- `matplotlib`: Chart and visualization generation (optional)
- `numpy`: Numerical operations (dependency of matplotlib)
- `aiofiles`: Async file I/O
- `beautifulsoup4`: HTML parsing

## Support

- [AstrBot Documentation](https://astrbot.app)
- [Plugin Development Guide](https://docs.astrbot.app/dev/star/)

## License

See [LICENSE](LICENSE) for details.
