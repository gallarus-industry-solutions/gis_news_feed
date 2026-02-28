# File: bot/ai/__init__.py
"""AI-powered summarization and content curation via Google Gemini."""

from bot.ai.summarizer import (
    SummarizedArticle,
    FeaturedVideo,
    summarize_articles,
    generate_editorial_intro,
    pick_featured_video,
)

__all__ = [
    "SummarizedArticle",
    "FeaturedVideo",
    "summarize_articles",
    "generate_editorial_intro",
    "pick_featured_video",
]
