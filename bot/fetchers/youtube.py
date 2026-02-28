# File: bot/fetchers/youtube.py
"""
Fetches educational videos from curated YouTube channels via RSS
and optionally the YouTube Data API v3.

Dual-source strategy:
  1. Channel RSS (primary, no API key) — polls curated channel feeds
  2. YouTube Data API (optional) — keyword search across all of YouTube
"""

import feedparser
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from bot.config import (
    YOUTUBE_API_KEY,
    YOUTUBE_CHANNELS,
    YOUTUBE_SEARCH_QUERIES,
    MAX_VIDEOS,
    MAX_VIDEO_AGE_HOURS,
)

logger = logging.getLogger(__name__)

_CHANNEL_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
_VIDEO_ID_RE = re.compile(r"(?:v=|/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})")


@dataclass
class VideoCandidate:
    """A YouTube video that may be featured in the digest."""

    title: str
    url: str
    channel_name: str
    published: Optional[datetime] = None
    description: str = ""
    thumbnail_url: str = ""

    @property
    def video_id(self) -> str:
        """Extract the 11-char YouTube video ID, or fall back to a URL hash."""
        match = _VIDEO_ID_RE.search(self.url)
        return match.group(1) if match else hashlib.md5(self.url.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Channel RSS fetcher (no API key needed)
# ---------------------------------------------------------------------------

def _fetch_channel_rss() -> list[VideoCandidate]:
    """Fetch recent uploads from curated YouTube channels via RSS."""
    videos: list[VideoCandidate] = []

    for channel_id, channel_name in YOUTUBE_CHANNELS.items():
        feed_url = _CHANNEL_RSS.format(channel_id=channel_id)
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:  # latest 5 per channel
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                video_id = getattr(entry, "yt_videoid", "")
                url = entry.get("link", "")
                if not video_id and url:
                    m = _VIDEO_ID_RE.search(url)
                    video_id = m.group(1) if m else ""

                description = entry.get("summary", "")[:500]
                thumbnail = (
                    f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    if video_id else ""
                )

                videos.append(VideoCandidate(
                    title=entry.get("title", "Untitled"),
                    url=url,
                    channel_name=channel_name,
                    published=pub_date,
                    description=description,
                    thumbnail_url=thumbnail,
                ))
            logger.info(f"YouTube RSS: {len(feed.entries)} videos from {channel_name}")
        except Exception as exc:
            logger.warning(f"YouTube RSS failed for {channel_name}: {exc}")
        time.sleep(0.3)

    return videos


# ---------------------------------------------------------------------------
# YouTube Data API v3 fetcher (optional)
# ---------------------------------------------------------------------------

def _fetch_youtube_api() -> list[VideoCandidate]:
    """Search YouTube via Data API v3. Requires YOUTUBE_API_KEY."""
    if not YOUTUBE_API_KEY:
        logger.debug("YOUTUBE_API_KEY not set — skipping API search.")
        return []

    try:
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning(
            "google-api-python-client not installed. "
            "Run: pip install google-api-python-client"
        )
        return []

    videos: list[VideoCandidate] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_VIDEO_AGE_HOURS)

    try:
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        for query in YOUTUBE_SEARCH_QUERIES[:3]:  # conserve quota
            try:
                request = youtube.search().list(
                    q=query,
                    part="snippet",
                    type="video",
                    maxResults=5,
                    order="date",
                    publishedAfter=cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    relevanceLanguage="en",
                    videoDuration="medium",  # 4–20 min
                )
                response = request.execute()

                for item in response.get("items", []):
                    snippet = item.get("snippet", {})
                    vid = item.get("id", {}).get("videoId", "")
                    pub_date = _parse_iso(snippet.get("publishedAt"))

                    videos.append(VideoCandidate(
                        title=snippet.get("title", "Untitled"),
                        url=f"https://www.youtube.com/watch?v={vid}",
                        channel_name=snippet.get("channelTitle", "Unknown"),
                        published=pub_date,
                        description=snippet.get("description", "")[:500],
                        thumbnail_url=(
                            snippet.get("thumbnails", {})
                            .get("high", {})
                            .get("url", "")
                        ),
                    ))
                logger.info(
                    f"YouTube API '{query}': "
                    f"{len(response.get('items', []))} results"
                )
            except Exception as exc:
                logger.warning(f"YouTube API query '{query}' failed: {exc}")
            time.sleep(0.3)
    except Exception as exc:
        logger.error(f"YouTube API client init failed: {exc}")

    return videos


def _parse_iso(iso_string: Optional[str]) -> Optional[datetime]:
    if not iso_string:
        return None
    try:
        return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Pipeline: fetch → deduplicate → filter → sort → truncate
# ---------------------------------------------------------------------------

def _deduplicate(videos: list[VideoCandidate]) -> list[VideoCandidate]:
    seen: set[str] = set()
    unique: list[VideoCandidate] = []
    for v in videos:
        vid = v.video_id
        if v.url and vid not in seen:
            seen.add(vid)
            unique.append(v)
    return unique


def _filter_by_age(videos: list[VideoCandidate]) -> list[VideoCandidate]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_VIDEO_AGE_HOURS)
    return [v for v in videos if v.published is None or v.published >= cutoff]


def fetch_youtube_videos() -> list[VideoCandidate]:
    """
    Main entry point. Fetches from all YouTube sources, deduplicates,
    filters by age, sorts newest-first, and truncates to MAX_VIDEOS.
    """
    logger.info("Fetching YouTube videos...")

    rss_videos = _fetch_channel_rss()
    api_videos = _fetch_youtube_api()

    combined = rss_videos + api_videos
    combined = _deduplicate(combined)
    combined = _filter_by_age(combined)
    combined.sort(
        key=lambda v: v.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    logger.info(
        f"YouTube total: {len(combined)} videos "
        f"(RSS: {len(rss_videos)}, API: {len(api_videos)})"
    )
    return combined[:MAX_VIDEOS]
