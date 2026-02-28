# File: lambda_handler.py
"""
AWS Lambda entry point for the Gallarus Intelligence Bulletin.

EventBridge triggers this daily. Secrets are loaded from environment
variables (set via Terraform from SSM Parameter Store).
"""

import logging
import sys

# Lambda pre-configures the root logger; reconfigure for our format.
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Remove default Lambda handler and add our own
for h in logger.handlers:
    logger.removeHandler(h)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logger.addHandler(handler)

from bot.fetchers import fetch_all_news, fetch_youtube_videos
from bot.ai import (
    summarize_articles,
    generate_editorial_intro,
    pick_featured_video,
)
from bot.delivery import publish_to_teams
from bot.cache import filter_unseen, mark_seen


def handler(event: dict, context: object) -> dict:
    """Lambda entry point. Mirrors run_digest() from main.py."""
    log = logging.getLogger("ai_news_bot")
    log.info("Lambda invoked — starting digest generation.")

    # 1 — Fetch
    articles = fetch_all_news()
    if not articles:
        log.warning("No articles found.")
        return {"statusCode": 200, "body": "No articles found."}

    # 2 — Dedup
    unseen = filter_unseen([a.url_hash for a in articles])
    articles = [a for a in articles if a.url_hash in unseen]
    if not articles:
        log.info("All articles already sent.")
        return {"statusCode": 200, "body": "All articles already sent."}
    log.info(f"New articles: {len(articles)}")

    # 3 — Summarize
    summarized = summarize_articles(articles)
    if not summarized:
        log.warning("Summarization returned no results.")
        return {"statusCode": 500, "body": "Summarization failed."}

    # 4 — Editorial intro
    intro = generate_editorial_intro(summarized)

    # 5 — YouTube
    video_candidates = fetch_youtube_videos()
    featured_video = None
    if video_candidates:
        featured_video = pick_featured_video(video_candidates)

    # 6 — Publish
    success = publish_to_teams(summarized, intro, featured_video)
    if success:
        mark_seen([a.url_hash for a in articles])
        log.info("Digest published.")
        return {"statusCode": 200, "body": f"Published {len(summarized)} articles."}

    log.error("Failed to publish.")
    return {"statusCode": 500, "body": "Publish failed."}
