"""
Async Bilibili API client using UAPI (uapis.cn).

Provides functions to fetch video information and user archives.

API docs:
- https://uapis.cn/docs/api-reference/get-social-bilibili-videoinfo
- https://uapis.cn/docs/api-reference/get-social-bilibili-archives
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict, cast

import aiohttp

UAPI_VIDEOINFO_URL = "https://uapis.cn/api/v1/social/bilibili/videoinfo"
UAPI_ARCHIVES_URL = "https://uapis.cn/api/v1/social/bilibili/archives"


class UapiResponse(TypedDict, total=False):
    """Type definition for UAPI response."""
    code: int
    message: str
    data: dict[str, Any]


@dataclass(slots=True)
class BilibiliDescription:
    """Bilibili video description data."""
    aid: int | None
    bvid: str | None
    title: str | None
    desc: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "aid": self.aid,
            "bvid": self.bvid,
            "title": self.title,
            "desc": self.desc,
        }


def _is_bvid(s: str) -> bool:
    """Check if string is a BVID."""
    return s.upper().startswith("BV")


def _extract_desc(data: dict[str, Any]) -> BilibiliDescription:
    """Extract description from API response data."""
    aid = data.get("aid") if isinstance(data.get("aid"), int) else None
    bvid = data.get("bvid") if isinstance(data.get("bvid"), str) else None
    title = data.get("title") if isinstance(data.get("title"), str) else None
    desc = None

    # Try multiple possible locations for description
    for key in ("desc", "description", "dynamic"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            desc = val.strip()
            break

    # Some APIs may nest details under "data" again (double-wrapped)
    if desc is None and isinstance(data.get("data"), dict):
        inner = data["data"]
        for key in ("desc", "description", "dynamic"):
            val = inner.get(key)
            if isinstance(val, str) and val.strip():
                desc = val.strip()
                break
        if title is None and isinstance(inner.get("title"), str):
            title = inner["title"]
        if aid is None and isinstance(inner.get("aid"), int):
            aid = inner["aid"]
        if bvid is None and isinstance(inner.get("bvid"), str):
            bvid = inner["bvid"]

    return BilibiliDescription(aid=aid, bvid=bvid, title=title, desc=desc)


async def fetch_videoinfo(identifier: str, *, timeout: float = 10.0) -> UapiResponse:
    """
    Fetch video information from UAPI.
    
    Args:
        identifier: BVID (BV...) or numeric AID
        timeout: Request timeout in seconds
        
    Returns:
        UAPI response dictionary
        
    Raises:
        ValueError: If identifier format is invalid
        RuntimeError: If response structure is unexpected
    """
    params: dict[str, str]
    match identifier:
        case s if _is_bvid(s):
            params = {"bvid": s}
        case s if s.isdigit():
            params = {"aid": s}
        case _:
            raise ValueError("identifier must be a bvid (BV...) or numeric aid")

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout),
        headers={
            "Accept": "application/json",
            "User-Agent": "astrbot-sast-plugin/2.0 (+https://github.com/AstroAir/astrbot_sast_plugin)",
        },
    ) as session:
        async with session.get(UAPI_VIDEOINFO_URL, params=params) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
            if not isinstance(payload, dict):
                raise RuntimeError("Unexpected response structure from uapis.cn")
            return payload  # type: ignore[return-value]


async def get_bilibili_description(identifier: str) -> BilibiliDescription:
    """
    Get Bilibili video description.
    
    Args:
        identifier: BVID (BV...) or numeric AID
        
    Returns:
        BilibiliDescription object with video metadata
        
    Raises:
        ValueError: If identifier format is invalid
        RuntimeError: If unable to parse response
    """
    payload = await fetch_videoinfo(identifier)

    # UAPI typically wraps result as { code, message, data }
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        return _extract_desc(data)
    # Fallback if API returns raw data
    if isinstance(payload, dict):
        return _extract_desc(cast(dict[str, Any], payload))
    raise RuntimeError("Unable to parse videoinfo response")


async def fetch_archives(
    mid: str,
    *,
    keywords: str | None = None,
    orderby: str = "pubdate",
    ps: int = 20,
    pn: int = 1,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """
    Fetch user's video archives from UAPI.
    
    Args:
        mid: User's MID (member ID)
        keywords: Optional search keywords
        orderby: Sort order (default: "pubdate")
        ps: Page size (default: 20)
        pn: Page number (default: 1)
        timeout: Request timeout in seconds
        
    Returns:
        Archives data dictionary containing videos list
        
    Raises:
        RuntimeError: If response structure is unexpected
    """
    params: dict[str, str] = {
        "mid": mid,
        "orderby": orderby,
        "ps": str(ps),
        "pn": str(pn),
    }
    if keywords:
        params["keywords"] = keywords

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout),
        headers={
            "Accept": "application/json",
            "User-Agent": "astrbot-sast-plugin/2.0 (+https://github.com/AstroAir/astrbot_sast_plugin)",
        },
    ) as session:
        async with session.get(UAPI_ARCHIVES_URL, params=params) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
            if not isinstance(payload, dict):
                raise RuntimeError("Unexpected archives response structure from uapis.cn")
            data = payload.get("data") if isinstance(payload, dict) else None
            return cast(dict[str, Any], data if isinstance(data, dict) else payload)


def pick_latest_from_archives(archives: dict[str, Any]) -> dict[str, Any]:
    """
    Extract the latest video from archives response.
    
    Args:
        archives: Archives data from fetch_archives()
        
    Returns:
        Latest video data dictionary
        
    Raises:
        RuntimeError: If no videos found in archives
    """
    videos = archives.get("videos")
    if isinstance(videos, list) and videos:
        first = videos[0]
        if isinstance(first, dict):
            return first
    raise RuntimeError("No videos found for this user (archives empty)")

