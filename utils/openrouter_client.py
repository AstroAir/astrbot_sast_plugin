"""
OpenRouter summarization client using minimax/minimax-m2:free.

Docs:
- OpenRouter Chat Completions: https://openrouter.ai/docs
- Model: https://openrouter.ai/minimax/minimax-m2:free
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT = f"{OPENROUTER_BASE}/chat/completions"
DEFAULT_MODEL = "minimax/minimax-m2:free"


@dataclass(slots=True)
class ORSummaryOptions:
    """Options for OpenRouter summarization."""
    api_key: str
    model: str = DEFAULT_MODEL
    temperature: float = 0.2
    max_tokens: int | None = None
    language: str = "zh"  # output language: zh/en


def build_summary_prompt(content: str, url: str | None = None, *, language: str = "zh") -> list[dict[str, str]]:
    """
    Build prompt messages for summarization.
    
    Args:
        content: Content to summarize
        url: Optional source URL
        language: Output language (zh/en)
        
    Returns:
        List of message dictionaries for chat completion
    """
    system_cn = (
        "你是一个专业的信息整理助手。请用简洁的要点总结输入网页的核心信息，"
        "包含：主题、关键信息点（使用项目符号）、重要数据/结论、作者或发布日期（若有），"
        "并给出3-5条高价值要点。保持客观、准确、可读，避免冗长。"
    )
    system_en = (
        "You are a helpful summarizer. Provide a concise, objective summary of the provided web page, "
        "including topic, key bullet points, notable data/findings, author/date (if available), "
        "and 3-5 high-value takeaways. Keep it accurate and scannable."
    )
    system = system_cn if language.lower().startswith("zh") else system_en

    user_prefix = f"Source: {url}\n\n" if url else ""
    user = (
        f"{user_prefix}Content to summarize (may be truncated):\n\n" + content
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def openrouter_chat(messages: list[dict[str, str]], opts: ORSummaryOptions) -> dict[str, Any]:
    """
    Call OpenRouter chat completion API.
    
    Args:
        messages: List of message dictionaries
        opts: OpenRouter options
        
    Returns:
        API response dictionary
        
    Raises:
        RuntimeError: If response format is unexpected
    """
    headers = {
        "Authorization": f"Bearer {opts.api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/AstroAir/astrbot_sast_plugin",
        "X-Title": "astrbot_sast_plugin summarizer",
        "User-Agent": "astrbot-sast-plugin/2.0",
    }
    payload: dict[str, Any] = {
        "model": opts.model,
        "messages": messages,
        "temperature": opts.temperature,
    }
    if opts.max_tokens is not None:
        payload["max_tokens"] = opts.max_tokens

    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as session:
        async with session.post(OPENROUTER_CHAT, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            if not isinstance(data, dict):
                raise RuntimeError("Unexpected OpenRouter response format")
            return data


def extract_choice_text(data: dict[str, Any]) -> str | None:
    """
    Extract text content from OpenRouter response.
    
    Args:
        data: API response dictionary
        
    Returns:
        Extracted text or None if not found
    """
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str):
                return content
    return None


async def summarize_batch(texts: list[tuple[str | None, str]], opts: ORSummaryOptions) -> list[dict[str, Any]]:
    """
    Summarize a batch of (url, content) pairs.
    
    Args:
        texts: List of (url, content) tuples
        opts: OpenRouter options
        
    Returns:
        List of dictionaries with url, summary, and raw_response
    """
    results: list[dict[str, Any]] = []
    for url, content in texts:
        messages = build_summary_prompt(content, url, language=opts.language)
        data = await openrouter_chat(messages, opts)
        summary = extract_choice_text(data)
        results.append({
            "url": url,
            "summary": summary,
            "raw": data,
        })
    return results

