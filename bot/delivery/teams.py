# File: bot/delivery/teams.py
"""
Publishes the Gallarus Intelligence Bulletin to Microsoft Teams via
Incoming Webhook using Adaptive Cards (v1.4).

Balances visual richness with Teams' ~28KB webhook payload limit.
"""

import json
import logging
import requests
from datetime import datetime, timezone
from typing import Optional

from bot.config import TEAMS_WEBHOOK_URL, DIGEST_TITLE, DIGEST_SUBTITLE
from bot.ai.summarizer import SummarizedArticle, FeaturedVideo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category labels & styles
# ---------------------------------------------------------------------------

_CATEGORIES: dict[str, dict[str, str]] = {
    "edge_computing": {"label": "\u26a1 Edge & Infrastructure", "style": "attention"},
    "manufacturing":  {"label": "\U0001f3ed Smart Manufacturing",  "style": "good"},
    "general_ai":     {"label": "\U0001f52e Innovation Horizon",   "style": "accent"},
}

_CATEGORY_ORDER = ["edge_computing", "manufacturing", "general_ai"]


def _truncate(text: str, max_len: int) -> str:
    """Truncate at word boundary with ellipsis."""
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:!?") + "\u2026"


# ---------------------------------------------------------------------------
# Card builders
# ---------------------------------------------------------------------------

def _build_card_body(
    articles: list[SummarizedArticle],
    intro: str,
    featured_video: Optional[FeaturedVideo] = None,
) -> list[dict]:
    """Build the card body — styled containers + compact article blocks."""
    now = datetime.now(timezone.utc)
    body: list[dict] = []

    # ── Header banner ──────────────────────────────────────────────
    body.append({
        "type": "Container",
        "style": "emphasis",
        "bleed": True,
        "items": [
            {
                "type": "TextBlock",
                "text": DIGEST_TITLE,
                "weight": "bolder",
                "size": "large",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": DIGEST_SUBTITLE,
                "isSubtle": True,
                "spacing": "none",
                "size": "small",
            },
            {
                "type": "TextBlock",
                "text": (
                    f"\U0001f4c5 {now.strftime('%A, %B %d, %Y')}"
                    f"  \u2022  \U0001f4ca {len(articles)} dispatches"
                ),
                "isSubtle": True,
                "spacing": "small",
                "size": "small",
            },
        ],
    })

    # ── Editorial intro ────────────────────────────────────────────
    body.append({
        "type": "TextBlock",
        "text": f"*\"{intro[:300]}\"*",
        "wrap": True,
        "spacing": "medium",
        "isSubtle": True,
    })

    # ── Articles by category ───────────────────────────────────────
    grouped: dict[str, list[SummarizedArticle]] = {}
    for a in articles:
        grouped.setdefault(a.category, []).append(a)

    sorted_cats = sorted(
        grouped.keys(),
        key=lambda c: _CATEGORY_ORDER.index(c) if c in _CATEGORY_ORDER else 99,
    )

    num = 1
    for cat in sorted_cats:
        meta = _CATEGORIES.get(cat, {"label": cat.title(), "style": "default"})
        cat_articles = grouped[cat]

        # Category header — colored container
        body.append({
            "type": "Container",
            "style": meta["style"],
            "bleed": True,
            "spacing": "large",
            "items": [{
                "type": "TextBlock",
                "text": f"**{meta['label']}**  \u2014  {len(cat_articles)} {'dispatch' if len(cat_articles) == 1 else 'dispatches'}",
                "size": "medium",
                "wrap": True,
            }],
        })

        for article in cat_articles:
            summary = _truncate(article.summary or "", 200)
            takeaway = _truncate(article.key_takeaway or "", 140)

            # Article title
            body.append({
                "type": "TextBlock",
                "text": f"**{num}. [{article.title[:90]}]({article.url})**",
                "wrap": True,
                "spacing": "medium",
                "separator": True,
            })

            # Source badge
            body.append({
                "type": "TextBlock",
                "text": f"\U0001f4f0 {article.source}",
                "isSubtle": True,
                "spacing": "none",
                "size": "small",
            })

            # Summary
            body.append({
                "type": "TextBlock",
                "text": summary,
                "wrap": True,
                "spacing": "small",
                "size": "small",
            })

            # Takeaway in emphasis container
            if takeaway:
                body.append({
                    "type": "Container",
                    "style": "emphasis",
                    "items": [{
                        "type": "TextBlock",
                        "text": f"\u2192 **Takeaway:** {takeaway}",
                        "wrap": True,
                        "size": "small",
                    }],
                    "spacing": "small",
                })

            num += 1

    # ── Featured video ─────────────────────────────────────────────
    if featured_video:
        # Section header
        body.append({
            "type": "Container",
            "style": "accent",
            "bleed": True,
            "spacing": "large",
            "items": [
                {
                    "type": "TextBlock",
                    "text": "**\U0001f393 Featured Learning**",
                    "size": "medium",
                },
                {
                    "type": "TextBlock",
                    "text": "Curated for the Gallarus engineering team",
                    "isSubtle": True,
                    "spacing": "none",
                    "size": "small",
                },
            ],
        })

        # Thumbnail
        if featured_video.thumbnail_url:
            body.append({
                "type": "Image",
                "url": featured_video.thumbnail_url,
                "size": "large",
                "horizontalAlignment": "center",
                "spacing": "medium",
                "selectAction": {
                    "type": "Action.OpenUrl",
                    "url": featured_video.url,
                },
            })

        # Video title + channel
        body.append({
            "type": "TextBlock",
            "text": f"**{featured_video.title}**",
            "wrap": True,
            "spacing": "small",
        })
        body.append({
            "type": "TextBlock",
            "text": f"\U0001f4fa {featured_video.channel_name}",
            "isSubtle": True,
            "spacing": "none",
            "size": "small",
        })

        # Description + reason
        desc = _truncate(featured_video.description or "", 220)
        reason = _truncate(featured_video.reason or "", 160)
        if desc:
            body.append({
                "type": "TextBlock",
                "text": desc,
                "wrap": True,
                "spacing": "small",
                "size": "small",
            })
        if reason:
            body.append({
                "type": "Container",
                "style": "emphasis",
                "items": [{
                    "type": "TextBlock",
                    "text": f"\u2192 **Why this matters:** {reason}",
                    "wrap": True,
                    "size": "small",
                }],
                "spacing": "small",
            })

        # Watch button
        body.append({
            "type": "ActionSet",
            "spacing": "small",
            "actions": [{
                "type": "Action.OpenUrl",
                "title": "\u25b6\ufe0f  Watch on YouTube",
                "url": featured_video.url,
            }],
        })

    # ── Footer ─────────────────────────────────────────────────────
    body.append({
        "type": "Container",
        "style": "emphasis",
        "bleed": True,
        "spacing": "large",
        "items": [{
            "type": "TextBlock",
            "text": (
                f"\u269b\ufe0f Gallarus Intelligence  \u2022  "
                f"{now.strftime('%H:%M UTC')}  \u2022  "
                f"[gis.ie](https://gis.ie)"
            ),
            "isSubtle": True,
            "size": "small",
            "horizontalAlignment": "center",
        }],
    })

    return body


# ---------------------------------------------------------------------------
# Card assembly & HTTP delivery
# ---------------------------------------------------------------------------

def build_adaptive_card(
    articles: list[SummarizedArticle],
    intro: str,
    featured_video: Optional[FeaturedVideo] = None,
) -> dict:
    """Assemble the complete Adaptive Card JSON payload."""
    body = _build_card_body(articles, intro, featured_video)
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": body,
            },
        }],
    }


def publish_to_teams(
    articles: list[SummarizedArticle],
    intro: str,
    featured_video: Optional[FeaturedVideo] = None,
) -> bool:
    """Post the Gallarus Intelligence Bulletin to Teams via webhook."""
    if not TEAMS_WEBHOOK_URL:
        logger.error("TEAMS_WEBHOOK_URL not configured.")
        return False

    card = build_adaptive_card(articles, intro, featured_video)
    payload_size = len(json.dumps(card).encode("utf-8"))
    logger.info(f"Card payload size: {payload_size:,} bytes")

    try:
        resp = requests.post(
            TEAMS_WEBHOOK_URL,
            json=card,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        body = resp.text

        if resp.status_code in (200, 202) and "error" not in body.lower():
            logger.info(f"Posted to Teams. Status: {resp.status_code}")
            return True

        logger.error(
            f"Teams webhook failed. Status: {resp.status_code}, "
            f"Body: {body[:300]}"
        )
        return False

    except Exception as exc:
        logger.error(f"Teams POST failed: {exc}")
        return False
