"""
Link extraction utilities for finding Bilibili video links in content.

Extracts and validates Bilibili video URLs from text content.
"""
import re
from typing import Pattern


# Bilibili URL patterns
BILIBILI_PATTERNS: list[Pattern] = [
    # BV ID format: https://www.bilibili.com/video/BVxxxxxxxxxx
    re.compile(r'https?://(?:www\.)?bilibili\.com/video/(BV[a-zA-Z0-9]+)', re.IGNORECASE),
    # AV ID format: https://www.bilibili.com/video/avxxxxxxxxx
    re.compile(r'https?://(?:www\.)?bilibili\.com/video/(av\d+)', re.IGNORECASE),
    # Short link format: https://b23.tv/xxxxxxx
    re.compile(r'https?://b23\.tv/([a-zA-Z0-9]+)', re.IGNORECASE),
    # Mobile format: https://m.bilibili.com/video/BVxxxxxxxxxx
    re.compile(r'https?://m\.bilibili\.com/video/(BV[a-zA-Z0-9]+)', re.IGNORECASE),
]


def extract_bilibili_links(text: str) -> list[str]:
    """
    Extract Bilibili video links from text.
    
    Args:
        text: Text content to search for Bilibili links
        
    Returns:
        List of unique Bilibili video URLs found in the text
    """
    if not text:
        return []
    
    links = []
    seen = set()
    
    for pattern in BILIBILI_PATTERNS:
        matches = pattern.finditer(text)
        for match in matches:
            url = match.group(0)
            # Normalize URL
            normalized = normalize_bilibili_url(url)
            if normalized and normalized not in seen:
                links.append(normalized)
                seen.add(normalized)
    
    return links


def normalize_bilibili_url(url: str) -> str | None:
    """
    Normalize a Bilibili URL to standard format.
    
    Args:
        url: Bilibili URL to normalize
        
    Returns:
        Normalized URL or None if invalid
    """
    if not url:
        return None
    
    # Extract video ID
    for pattern in BILIBILI_PATTERNS:
        match = pattern.search(url)
        if match:
            video_id = match.group(1)
            
            # Handle short links (b23.tv) - these need to be resolved
            # For now, just return the original URL
            if 'b23.tv' in url:
                return url
            
            # Normalize to standard format
            if video_id.startswith('BV') or video_id.startswith('av'):
                return f"https://www.bilibili.com/video/{video_id}"
    
    return None


def extract_video_id(url: str) -> str | None:
    """
    Extract video ID (BV or AV) from Bilibili URL.
    
    Args:
        url: Bilibili URL
        
    Returns:
        Video ID (e.g., "BV1xx411c7mD" or "av12345") or None if not found
    """
    if not url:
        return None
    
    for pattern in BILIBILI_PATTERNS:
        match = pattern.search(url)
        if match:
            video_id = match.group(1)
            if video_id.startswith('BV') or video_id.startswith('av'):
                return video_id
    
    return None


def is_bilibili_url(url: str) -> bool:
    """
    Check if a URL is a Bilibili video URL.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is a Bilibili video URL
    """
    if not url:
        return False
    
    for pattern in BILIBILI_PATTERNS:
        if pattern.search(url):
            return True
    
    return False


def deduplicate_links(links: list[str]) -> list[str]:
    """
    Remove duplicate Bilibili links based on video ID.
    
    Args:
        links: List of Bilibili URLs
        
    Returns:
        Deduplicated list of URLs
    """
    seen_ids = set()
    unique_links = []
    
    for link in links:
        video_id = extract_video_id(link)
        if video_id and video_id not in seen_ids:
            seen_ids.add(video_id)
            unique_links.append(link)
        elif not video_id:
            # Keep links without extractable IDs (e.g., short links)
            unique_links.append(link)
    
    return unique_links

