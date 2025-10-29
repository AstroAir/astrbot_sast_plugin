"""
Tavily Extract API client.

Docs: https://docs.tavily.com/documentation/api-reference/endpoint/extract
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import aiohttp

TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"


@dataclass(slots=True)
class TavilyOptions:
    """Options for Tavily Extract API."""
    api_key: str
    extract_depth: str = "basic"  # basic | advanced
    format: str = "markdown"  # markdown | text
    include_images: bool = False
    include_favicon: bool = False
    timeout: float | None = None  # seconds (1-60) or None


def extract_urls(text: str) -> list[str]:
    """
    Find http(s) URLs in free text.
    
    Args:
        text: Text to search for URLs
        
    Returns:
        List of unique URLs found in text
    """
    if not text:
        return []
    # Basic URL regex
    pattern = re.compile(r"https?://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+", re.IGNORECASE)
    urls = pattern.findall(text)
    # Dedup while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


async def tavily_extract(urls: list[str], opts: TavilyOptions) -> dict[str, Any]:
    """
    Extract content from URLs using Tavily API.
    
    Args:
        urls: List of URLs to extract content from
        opts: Tavily API options
        
    Returns:
        Dictionary with 'results' and 'failed_results' keys
        
    Raises:
        RuntimeError: If response format is unexpected
    """
    if not urls:
        return {"results": [], "failed_results": []}

    headers = {
        "Authorization": f"Bearer {opts.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "astrbot-sast-plugin/2.0 (+https://github.com/AstroAir/astrbot_sast_plugin)",
    }
    payload: dict[str, Any] = {
        "urls": urls,
        "include_images": opts.include_images,
        "include_favicon": opts.include_favicon,
        "extract_depth": opts.extract_depth,
        "format": opts.format,
    }
    if opts.timeout is not None:
        payload["timeout"] = float(opts.timeout)

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=(opts.timeout or 30.0)),
        headers=headers,
    ) as session:
        async with session.post(TAVILY_EXTRACT_URL, json=payload) as resp:
            # Treat 4xx/5xx as errors
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            if not isinstance(data, dict):
                raise RuntimeError("Unexpected Tavily extract response format")
            return data

