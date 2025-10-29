"""
Shared utility functions for command handlers.

Contains common logic for flag parsing, URL extraction, and AI summarization.
"""
from __future__ import annotations

import os
from typing import Any

from utils.tavily_client import extract_urls, tavily_extract, TavilyOptions
from utils.openrouter_client import summarize_batch, ORSummaryOptions


def parse_command_flags(argv: list[str]) -> dict[str, Any]:
    """
    Parse simple flags used by commands.
    
    Supported flags:
      --extract  (bool)
      --max N    (int)
      --depth basic|advanced
      --format markdown|text
      --summarize (bool)
      
    Args:
        argv: List of command arguments
        
    Returns:
        Dictionary with parsed flags and '_consumed' key indicating how many args were consumed
    """
    flags: dict[str, Any] = {
        "extract": False,
        "max": 3,
        "depth": "basic",
        "format": "markdown",
        "summarize": False,
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--extract", "--extract-links"):
            flags["extract"] = True
            i += 1
        elif a == "--summarize":
            flags["summarize"] = True
            i += 1
        elif a == "--max" and i + 1 < len(argv):
            try:
                flags["max"] = int(argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif a == "--depth" and i + 1 < len(argv):
            flags["depth"] = argv[i + 1]
            i += 2
        elif a == "--format" and i + 1 < len(argv):
            flags["format"] = argv[i + 1]
            i += 2
        else:
            # stop at first non-flag
            break
    flags["_consumed"] = i
    return flags


async def extract_and_summarize_urls(
    description: str,
    flags: dict[str, Any],
    tavily_api_key: str | None = None,
    openrouter_api_key: str | None = None,
) -> dict[str, Any]:
    """
    Extract URLs from description and optionally summarize them.
    
    This is the shared logic used by both /bili_desc and /bili_latest commands.
    
    Args:
        description: Video description text
        flags: Parsed command flags from parse_command_flags()
        tavily_api_key: Tavily API key (defaults to env var)
        openrouter_api_key: OpenRouter API key (defaults to env var)
        
    Returns:
        Dictionary with:
        - success: bool
        - message: str (user-facing message)
        - urls: list[str] (extracted URLs)
        - extracted_content: dict | None (Tavily response)
        - summaries: list[dict] | None (AI summaries)
        - error: str | None (error message if failed)
    """
    result: dict[str, Any] = {
        "success": False,
        "message": "",
        "urls": [],
        "extracted_content": None,
        "summaries": None,
        "error": None,
    }
    
    # Extract URLs
    urls = extract_urls(description)
    if not urls:
        result["message"] = "简介中未发现链接。"
        result["success"] = True
        return result
    
    urls = urls[: int(flags.get("max", 3))]
    result["urls"] = urls
    
    # Get API keys
    tkey = tavily_api_key or os.environ.get("TAVILY_API_KEY")
    if not tkey:
        result["message"] = "未配置 TAVILY_API_KEY，已找到链接：\n- " + "\n- ".join(urls)
        result["success"] = True
        return result
    
    # Extract content from URLs
    try:
        tdata = await tavily_extract(urls, TavilyOptions(
            api_key=tkey,
            extract_depth=str(flags.get("depth", "basic")),
            format=str(flags.get("format", "markdown")),
        ))
        result["extracted_content"] = tdata
    except Exception as e:
        result["error"] = f"链接内容提取失败：{e}"
        return result
    
    result["message"] = "已提取网页内容。"
    
    # Optionally summarize
    if not flags.get("summarize"):
        result["success"] = True
        return result
    
    okey = openrouter_api_key or os.environ.get("OPENROUTER_API_KEY")
    if not okey:
        result["message"] += "\n未配置 OPENROUTER_API_KEY，跳过 AI 总结。"
        result["success"] = True
        return result
    
    # Extract content pairs for summarization
    items = tdata.get("results") if isinstance(tdata, dict) else None
    pairs: list[tuple[str | None, str]] = []
    if isinstance(items, list):
        for it in items[: int(flags.get("max", 3))]:
            if isinstance(it, dict):
                url = it.get("url") if isinstance(it.get("url"), str) else None
                content = (
                    it.get("markdown")
                    or it.get("content")
                    or it.get("text")
                    or it.get("raw_content")
                )
                if isinstance(content, str) and content.strip():
                    pairs.append((url, content[:8000]))
    
    if not pairs:
        result["message"] += "\n未找到可供总结的正文内容。"
        result["success"] = True
        return result
    
    # Summarize
    try:
        sres = await summarize_batch(
            pairs,
            ORSummaryOptions(
                api_key=okey,
                model="minimax/minimax-m2:free",
                language="zh"
            )
        )
        result["summaries"] = sres
        result["success"] = True
        
        # Build summary message
        lines = ["AI 总结："]
        for item in sres:
            u = item.get("url") or "(no url)"
            summ = item.get("summary") or "(no summary)"
            lines.append(f"- {u}\n{summ}")
        result["message"] = "\n\n".join(lines)
        
    except Exception as e:
        result["error"] = f"AI 总结失败：{e}"
        return result
    
    return result


def format_summary_message(summaries: list[dict[str, Any]]) -> str:
    """
    Format AI summaries into a user-friendly message.
    
    Args:
        summaries: List of summary dictionaries from summarize_batch()
        
    Returns:
        Formatted message string
    """
    lines = ["AI 总结："]
    for item in summaries:
        u = item.get("url") or "(no url)"
        summ = item.get("summary") or "(no summary)"
        lines.append(f"- {u}\n{summ}")
    return "\n\n".join(lines)

