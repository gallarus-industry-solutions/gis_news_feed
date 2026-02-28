#!/usr/bin/env python3
# File: main.py
"""
AI News Bot — Daily digest of AI + manufacturing news with a featured
educational video, posted to Microsoft Teams via webhook.

Usage:
    python main.py              # Run once (for cron / scheduled task)
    python main.py --dry-run    # Fetch + summarize, print to stdout only
    python main.py --daemon     # Run continuously with built-in scheduler
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from bot.fetchers import fetch_all_news, fetch_youtube_videos
from bot.ai import (
    summarize_articles,
    generate_editorial_intro,
    pick_featured_video,
    FeaturedVideo,
    SummarizedArticle,
)
from bot.delivery import publish_to_teams
from bot.cache import filter_unseen, mark_seen

_LOG_FILE = Path(__file__).resolve().parent / "ai_news_bot.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_LOG_FILE),
    ],
)
logger = logging.getLogger("ai_news_bot")


# ---------------------------------------------------------------------------
# Core digest cycle
# ---------------------------------------------------------------------------

def run_digest(dry_run: bool = False) -> bool:
    """Execute one full digest cycle. Returns True on success."""
    logger.info("=" * 60)
    logger.info("Starting AI News Digest generation...")
    logger.info("=" * 60)

    # 1 — Fetch news articles
    articles = fetch_all_news()
    if not articles:
        logger.warning("No articles found. Skipping digest.")
        return False
    logger.info(f"Fetched {len(articles)} articles.")

    # 2 — Filter out previously sent articles
    unseen_hashes = filter_unseen([a.url_hash for a in articles])
    articles = [a for a in articles if a.url_hash in unseen_hashes]
    if not articles:
        logger.warning("All articles already sent. Skipping digest.")
        return False
    logger.info(f"New (unseen) articles: {len(articles)}")

    # 3 — Log category distribution
    cats: dict[str, int] = {}
    for a in articles:
        cats[a.category] = cats.get(a.category, 0) + 1
    logger.info(f"Categories: {cats}")

    # 4 — Summarize with Gemini
    summarized = summarize_articles(articles)
    if not summarized:
        logger.warning("Summarization returned no results.")
        return False

    # 5 — Editorial intro
    intro = generate_editorial_intro(summarized)

    # 6 — YouTube: fetch candidates → Gemini picks one
    video_candidates = fetch_youtube_videos()
    featured_video = None
    if video_candidates:
        logger.info(f"Found {len(video_candidates)} video candidates.")
        featured_video = pick_featured_video(video_candidates)
        if featured_video:
            logger.info(f"Featured video: {featured_video.title}")
    else:
        logger.info("No video candidates found — skipping video section.")

    # 7 — Deliver
    if dry_run:
        _print_dry_run(intro, summarized, featured_video)
        return True

    success = publish_to_teams(summarized, intro, featured_video)
    if success:
        # Mark articles as seen so they won't repeat tomorrow
        mark_seen([a.url_hash for a in articles])
        logger.info("Digest published successfully.")
    else:
        logger.error("Failed to publish digest.")
    return success


def _print_dry_run(
    intro: str,
    summarized: list[SummarizedArticle],
    featured_video: FeaturedVideo | None,
) -> None:
    """Pretty-print the digest to stdout for verification."""
    logger.info("=== DRY RUN OUTPUT ===")
    print(f"\n\U0001f4cb {intro}\n")

    for s in summarized:
        print(f"[{s.category}] {s.title}")
        print(f"  Source: {s.source}")
        print(f"  URL:    {s.url}")
        print(f"  Summary: {s.summary}")
        if s.key_takeaway:
            print(f"  Takeaway: {s.key_takeaway}")
        print()

    if featured_video:
        print("\U0001f393 Featured Learning:")
        print(f"  {featured_video.title}")
        print(f"  Channel:  {featured_video.channel_name}")
        print(f"  URL:      {featured_video.url}")
        print(f"  {featured_video.description}")
        print(f"  Why:      {featured_video.reason}")
    else:
        print("(No featured video this run)")


# ---------------------------------------------------------------------------
# Daemon mode
# ---------------------------------------------------------------------------

def run_daemon(target_hour: int = 7, target_minute: int = 0) -> None:
    """Run continuously; execute digest at target_hour:target_minute UTC daily."""
    logger.info(
        f"Daemon mode: posting daily at {target_hour:02d}:{target_minute:02d} UTC"
    )
    last_run_date = None

    while True:
        now = datetime.now(timezone.utc)
        today = now.date()

        if (
            now.hour == target_hour
            and now.minute >= target_minute
            and last_run_date != today
        ):
            try:
                run_digest(dry_run=False)
            except Exception as exc:
                logger.error(f"Digest failed: {exc}", exc_info=True)
            last_run_date = today

        time.sleep(30)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="AI News Bot for Teams")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print digest without posting to Teams",
    )
    parser.add_argument(
        "--daemon", action="store_true",
        help="Run continuously with built-in scheduler",
    )
    parser.add_argument(
        "--hour", type=int, default=7,
        help="UTC hour for daemon mode (default: 7)",
    )
    args = parser.parse_args()

    if args.daemon:
        run_daemon(target_hour=args.hour)
    else:
        success = run_digest(dry_run=args.dry_run)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        logger.critical(f"Unhandled error: {exc}", exc_info=True)
        sys.exit(1)
