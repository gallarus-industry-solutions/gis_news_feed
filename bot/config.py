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
    "AI edge computing",
    "artificial intelligence manufacturing",
    "AI industrial automation",
    "edge AI inference",
    "AI factory optimization",
    "machine learning IoT manufacturing",
    "AI news today",
]

# ---------------------------------------------------------------------------
# News — RSS feeds curated for AI / edge / manufacturing
# ---------------------------------------------------------------------------
RSS_FEEDS: list[str] = [
    # Google News topic searches
    "https://news.google.com/rss/search?q=AI+edge+computing&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=artificial+intelligence+manufacturing&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=edge+AI+inference&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+industrial+automation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=smart+manufacturing+AI&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=predictive+maintenance+AI&hl=en-US&gl=US&ceid=US:en",
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
    # Manufacturing & Industrial (verified working)
    "UC8wXC0ZCfGt3HaVLy_fdTQw": "Siemens",
    # AI Research & Education (verified working)
    "UCbfYPyITQ-7l4upoX8nvctg": "Two Minute Papers",
    "UCZHmQk67mSJgfCCTn7xBfew": "Yannic Kilcher",
    "UCNJ1Ymd5yFuUPtn21xtRbbw": "AI Explained",
    "UCsBjURrPoezykLs9EqgamOA": "Fireship",
    "UCVHFbqXqoYvEWM1Ddxl0QDg": "AI Jason",
    "UCZeYkbo-0anAiKRDMGU2phw": "The AI Advantage",
    "UCLXo7UDZvByw2ixzpQCufnA": "Welker Media",
    "UCo8bcnLyZH8tBIH9V1mLgqQ": "TheAIGRID",
}

# YouTube Data API keyword searches (used only when YOUTUBE_API_KEY is set)
YOUTUBE_SEARCH_QUERIES: list[str] = [
    "edge AI manufacturing tutorial",
    "Industry 4.0 artificial intelligence",
    "AI quality control factory",
    "smart manufacturing AI",
    "TinyML embedded AI",
    "predictive maintenance machine learning",
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
DIGEST_SUBTITLE: str = "Connection to Innovation \u2022 Your daily edge in AI & manufacturing"
