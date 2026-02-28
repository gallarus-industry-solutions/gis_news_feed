# File: bot/fetchers/__init__.py
"""News and video fetching from RSS, NewsAPI, and YouTube."""

from bot.fetchers.news import Article, fetch_all_news
from bot.fetchers.youtube import VideoCandidate, fetch_youtube_videos

__all__ = ["Article", "VideoCandidate", "fetch_all_news", "fetch_youtube_videos"]
