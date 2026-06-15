# File: bot/config.py
"""
Central configuration for AI News Bot.
All secrets and tunables are loaded from environment variables / .env file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level above this file)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
TEAMS_WEBHOOK_URL: str = os.getenv("TEAMS_WEBHOOK_URL", "")
NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")        # https://newsapi.org
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")   # optional

# ---------------------------------------------------------------------------
# Gemini Model
# ---------------------------------------------------------------------------
GEMINI_MODEL: str = "gemini-3-flash-preview"

# ---------------------------------------------------------------------------
# News — search queries for NewsAPI
# ---------------------------------------------------------------------------
SEARCH_QUERIES: list[str] = [
    "AI news today",
    "artificial intelligence trends",
    "large language models",
    "AI tools new release",
    "AI agents",
    "generative AI",
    "open source AI models",
]

# ---------------------------------------------------------------------------
# News — RSS feeds curated for AI / edge / manufacturing
# ---------------------------------------------------------------------------
RSS_FEEDS: list[str] = [
    # Google News topic searches
    "https://news.google.com/rss/search?q=artificial+intelligence+news&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+tools+new&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=large+language+models&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=generative+AI&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+agents+autonomous&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=open+source+AI+models&hl=en-US&gl=US&ceid=US:en",
    # Publication feeds
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
]

# ---------------------------------------------------------------------------
# YouTube — curated channels for manufacturing / edge AI / Industry 4.0
#
# To find a channel ID:
#   1. Go to the channel page on YouTube
#   2. View Page Source → search for "channel_id" or "externalId"
#   3. Or use https://commentpicker.com/youtube-channel-id.php
# ---------------------------------------------------------------------------
YOUTUBE_CHANNELS: dict[str, str] = {
    # AI Research & Education
    "UCbfYPyITQ-7l4upoX8nvctg": "Two Minute Papers",
    "UCZHmQk67mSJgfCCTn7xBfew": "Yannic Kilcher",
    "UCNJ1Ymd5yFuUPtn21xtRbbw": "AI Explained",
    "UCsBjURrPoezykLs9EqgamOA": "Fireship",
    "UCVHFbqXqoYvEWM1Ddxl0QDg": "AI Jason",
    "UCZeYkbo-0anAiKRDMGU2phw": "The AI Advantage",
    "UCLXo7UDZvByw2ixzpQCufnA": "Welker Media",
    "UCo8bcnLyZH8tBIH9V1mLgqQ": "TheAIGRID",
    # AI Tools & Dev
    "UCXZCJLdBC09xxGZ6gcdrc6A": "Matt Wolfe",
    "UC2WHjPDvbE6O328n17ZGcfg": "ForrestKnight",
    "UCmXmlB4-HJhA7-CVIHi9GIg": "WorldofAI",
}

# YouTube Data API keyword searches (used only when YOUTUBE_API_KEY is set)
YOUTUBE_SEARCH_QUERIES: list[str] = [
    "AI tools tutorial 2026",
    "large language models explained",
    "AI agents tutorial",
    "best new AI tools",
    "open source AI models",
    "generative AI tutorial",
]

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------
MAX_ARTICLES: int = 10  # kept low to fit Teams ~28KB webhook payload limit
MAX_ARTICLE_AGE_HOURS: int = 28
MAX_VIDEOS: int = 10
MAX_VIDEO_AGE_HOURS: int = 168  # 7 days — videos are less frequent than news

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
DIGEST_TITLE: str = "\u269b\ufe0f Gallarus Intelligence Bulletin"
DIGEST_SUBTITLE: str = "Connection to Innovation \u2022 Your daily edge in AI trends & tools"
