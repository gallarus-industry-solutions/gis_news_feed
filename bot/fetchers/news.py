# File: bot/fetchers/news.py
"""
Fetches news articles from RSS feeds and optionally NewsAPI.
Deduplicates by URL and filters by publication age.
"""

import feedparser
import hashlib
import logging
import requests
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    from googlenewsdecoder import new_decoderv1 as _decode_gnews
    _HAS_GNEWS_DECODER = True
except ImportError:
    _HAS_GNEWS_DECODER = False

from bot.config import (
    RSS_FEEDS,
    NEWS_API_KEY,
    SEARCH_QUERIES,
    MAX_ARTICLES,
    MAX_ARTICLE_AGE_HOURS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Google News URL resolver
# ---------------------------------------------------------------------------

def _resolve_google_news_url(url: str) -> str:
    """Decode Google News redirect URLs to actual article URLs.

    Google News RSS returns protobuf-encoded redirect URLs that don't work
    in Teams Adaptive Cards. This uses googlenewsdecoder to extract the
    real publisher URL.
    """
    if "news.google.com/rss/articles/" not in url:
        return url
    if not _HAS_GNEWS_DECODER:
        return url
    try:
        result = _decode_gnews(url)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
    except Exception as exc:
        logger.debug(f"Google News URL decode failed: {exc}")
    return url


@dataclass
class Article:
    """A news article fetched from RSS or NewsAPI."""

    title: str
    url: str
    source: str
    published: Optional[datetime] = None
    description: str = ""
    category: str = "general_ai"  # edge_computing | manufacturing | general_ai

    @property
    def url_hash(self) -> str:
        """Deterministic deduplication key derived from the canonical URL."""
        return hashlib.md5(self.url.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Keyword-based classifier — cheap alternative to routing through an LLM
# ---------------------------------------------------------------------------

_EDGE_KEYWORDS = [
    "edge computing", "edge ai", "edge inference", "on-device",
    "iot", "embedded ai", "tinyml", "edge deployment", "on-prem ai",
]
_MFG_KEYWORDS = [
    "manufactur", "factory", "industrial", "automation",
    "quality control", "predictive maintenance", "supply chain",
    "robotics", "digital twin", "smart factory", "industry 4.0",
    "warehouse", "assembly line", "cnc", "plc",
]


def _classify_article(article: Article) -> str:
    """Assign a topic bucket based on title + description keywords."""
    text = f"{article.title} {article.description}".lower()
    if any(kw in text for kw in _EDGE_KEYWORDS):
        return "edge_computing"
    if any(kw in text for kw in _MFG_KEYWORDS):
        return "manufacturing"
    return "general_ai"


_JUNK_TITLES = {"[removed]", "untitled", ""}


def _is_valid_article(article: Article) -> bool:
    """Reject articles with missing/junk titles or empty URLs."""
    if not article.url:
        return False
    if article.title.strip().lower() in _JUNK_TITLES:
        return False
    return True


# ---------------------------------------------------------------------------
# RSS fetcher
# ---------------------------------------------------------------------------

def _fetch_rss() -> list[Article]:
    """Fetch articles from all configured RSS feeds."""
    articles: list[Article] = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(
                feed_url,
                request_headers={"User-Agent": "GallarusNewsBot/1.0"},
            )
            if feed.bozo and not feed.entries:
                logger.warning(f"RSS feed malformed/unreachable: {feed_url[:60]}")
                continue

            for entry in feed.entries:
                pub_date = _parse_feed_date(entry)
                article = Article(
                    title=(entry.get("title") or "Untitled").strip(),
                    url=entry.get("link", ""),
                    source=feed.feed.get("title", feed_url),
                    published=pub_date,
                    description=(entry.get("summary") or "")[:500],
                )
                article.category = _classify_article(article)
                if _is_valid_article(article):
                    articles.append(article)
            logger.info(f"RSS: {len(feed.entries)} entries from {feed_url[:60]}")
        except Exception as exc:
            logger.warning(f"RSS fetch failed for {feed_url}: {exc}")
        time.sleep(0.5)

    return articles


def _parse_feed_date(entry: object) -> Optional[datetime]:
    """Extract a timezone-aware datetime from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
    return None


# ---------------------------------------------------------------------------
# NewsAPI fetcher
# ---------------------------------------------------------------------------

def _fetch_newsapi() -> list[Article]:
    """Fetch articles from NewsAPI (requires NEWS_API_KEY)."""
    if not NEWS_API_KEY:
        logger.info("NEWS_API_KEY not set — skipping NewsAPI.")
        return []

    articles: list[Article] = []
    from_date = (
        datetime.now(timezone.utc) - timedelta(hours=MAX_ARTICLE_AGE_HOURS)
    ).strftime("%Y-%m-%d")

    for query in SEARCH_QUERIES[:4]:  # limit to conserve free-tier quota
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "from": from_date,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": 5,
                    "apiKey": NEWS_API_KEY,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("articles", []):
                pub_date = _parse_iso_date(item.get("publishedAt"))
                article = Article(
                    title=(item.get("title") or "Untitled").strip(),
                    url=item.get("url", ""),
                    source=(item.get("source") or {}).get("name", "Unknown"),
                    published=pub_date,
                    description=(item.get("description") or "")[:500],
                )
                article.category = _classify_article(article)
                if _is_valid_article(article):
                    articles.append(article)

            logger.info(f"NewsAPI '{query}': {len(data.get('articles', []))} results")
        except Exception as exc:
            logger.warning(f"NewsAPI query '{query}' failed: {exc}")
        time.sleep(0.3)

    return articles


def _parse_iso_date(iso_string: Optional[str]) -> Optional[datetime]:
    if not iso_string:
        return None
    try:
        return datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Pipeline: fetch → deduplicate → filter → sort → truncate
# ---------------------------------------------------------------------------

def _deduplicate(articles: list[Article]) -> list[Article]:
    seen: set[str] = set()
    unique: list[Article] = []
    for a in articles:
        if a.url and a.url_hash not in seen:
            seen.add(a.url_hash)
            unique.append(a)
    return unique


def _filter_by_age(articles: list[Article]) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_ARTICLE_AGE_HOURS)
    return [a for a in articles if a.published is None or a.published >= cutoff]


def fetch_all_news() -> list[Article]:
    """
    Main entry point. Fetches from all news sources, deduplicates,
    filters by age, sorts newest-first, and truncates to MAX_ARTICLES.
    """
    logger.info("Fetching news from all sources...")

    rss_articles = _fetch_rss()
    api_articles = _fetch_newsapi()

    combined = rss_articles + api_articles
    combined = _deduplicate(combined)
    combined = _filter_by_age(combined)
    combined.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    logger.info(
        f"News total: {len(combined)} articles "
        f"(RSS: {len(rss_articles)}, API: {len(api_articles)})"
    )
    result = combined[:MAX_ARTICLES]

    # Resolve Google News redirect URLs only for final selection (avoids
    # resolving 600+ URLs — only the ~10 that will appear in the digest).
    for article in result:
        article.url = _resolve_google_news_url(article.url)

    return result
