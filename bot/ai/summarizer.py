# File: bot/ai/summarizer.py
"""
Uses Google Gemini API (google-genai SDK) to:
  1. Summarize news articles with key takeaways
  2. Generate an editorial intro paragraph
  3. Select a featured educational YouTube video

All LLM interactions are isolated here — swap the model by changing
GEMINI_MODEL in config.py.
"""

import json
import logging
import re
import time
from dataclasses import dataclass

from google import genai
from google.genai import types

from bot.config import GEMINI_API_KEY, GEMINI_MODEL
from bot.fetchers.news import Article
from bot.fetchers.youtube import VideoCandidate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini client init
# ---------------------------------------------------------------------------
_client: genai.Client | None = None

if GEMINI_API_KEY:
    _client = genai.Client(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set — summarization will fail.")


def _get_client() -> genai.Client:
    """Return the initialized Gemini client or raise with a clear message."""
    if _client is None:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Set it in your .env file or environment."
        )
    return _client


def _parse_json(raw: str) -> dict | list:
    """Parse JSON from Gemini output, handling common malformations."""
    text = raw.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def _json_config(max_tokens: int = 4096) -> types.GenerateContentConfig:
    """Config for structured JSON output with thinking disabled.

    Gemini 3+ models enable thinking by default, which prepends thought
    tokens and breaks response_mime_type="application/json". Setting
    thinking_budget=0 disables this.
    """
    return types.GenerateContentConfig(
        response_mime_type="application/json",
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )


def _text_config(max_tokens: int = 300) -> types.GenerateContentConfig:
    """Config for plain-text output with thinking disabled."""
    return types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )


def _call_gemini_with_retry(
    prompt: str,
    config: types.GenerateContentConfig,
    max_retries: int = 3,
) -> str:
    """Call Gemini with exponential backoff on transient errors (429, 503)."""
    client = _get_client()
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
            if response.text is None:
                raise ValueError("Gemini returned empty response text.")
            return response.text
        except Exception as exc:
            is_retryable = any(
                code in str(exc) for code in ("429", "503", "RESOURCE_EXHAUSTED")
            )
            if is_retryable and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    f"Gemini transient error (attempt {attempt + 1}): {exc}. "
                    f"Retrying in {wait}s..."
                )
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Unreachable")


# ---------------------------------------------------------------------------
# Data models produced by this module
# ---------------------------------------------------------------------------

@dataclass
class SummarizedArticle:
    """An article enriched with an AI-generated summary and takeaway."""

    title: str
    url: str
    source: str
    category: str
    summary: str
    key_takeaway: str


@dataclass
class FeaturedVideo:
    """A YouTube video selected by AI as the day's featured learning."""

    title: str
    url: str
    channel_name: str
    thumbnail_url: str
    description: str
    reason: str


# ---------------------------------------------------------------------------
# Article summarization
# ---------------------------------------------------------------------------

def summarize_articles(articles: list[Article]) -> list[SummarizedArticle]:
    """Batch-summarize articles via Gemini. Returns structured summaries."""
    if not articles:
        logger.warning("No articles to summarize.")
        return []

    articles_block = "\n".join(
        f"--- Article {i + 1} ---\n"
        f"Title: {a.title}\n"
        f"Source: {a.source}\n"
        f"URL: {a.url}\n"
        f"Category: {a.category}\n"
        f"Published: {a.published.isoformat() if a.published else 'Unknown'}\n"
        f"Description: {a.description}\n"
        for i, a in enumerate(articles)
    )

    prompt = (
        "You are an AI news analyst specializing in edge computing, "
        "manufacturing AI, and broader AI industry trends.\n\n"
        f"Below are {len(articles)} recent news articles. For each, produce:\n"
        "1. A summary: EXACTLY 3 sentences, MAX 50 words total\n"
        "2. A key takeaway: EXACTLY 1 sentence, MAX 20 words, focused on business/technical impact\n\n"
        "STRICT: Do NOT exceed the word limits. Be punchy and direct.\n\n"
        "Respond ONLY with a JSON array. Each element:\n"
        '{"index": <number starting from 1>, '
        '"summary": "<3 sentences, max 50 words>", '
        '"key_takeaway": "<1 sentence, max 20 words>"}\n\n'
        f"Articles:\n{articles_block}"
    )

    try:
        client = _get_client()
        raw = _call_gemini_with_retry(prompt, _json_config(max_tokens=4096))
        summaries_data = _parse_json(raw)

        summarized: list[SummarizedArticle] = []
        for item in summaries_data:
            idx = item["index"] - 1
            if 0 <= idx < len(articles):
                a = articles[idx]
                summarized.append(SummarizedArticle(
                    title=a.title,
                    url=a.url,
                    source=a.source,
                    category=a.category,
                    summary=item.get("summary", "Summary unavailable."),
                    key_takeaway=item.get("key_takeaway", ""),
                ))

        logger.info(f"Summarized {len(summarized)} articles.")
        return summarized

    except json.JSONDecodeError as exc:
        logger.error(f"Gemini JSON parse failed: {exc}")
        return _fallback_summaries(articles)
    except Exception as exc:
        logger.error(f"Gemini API call failed: {exc}")
        raise


def _fallback_summaries(articles: list[Article]) -> list[SummarizedArticle]:
    """Return articles with their raw description as the summary."""
    return [
        SummarizedArticle(
            title=a.title,
            url=a.url,
            source=a.source,
            category=a.category,
            summary=a.description or "Summary unavailable.",
            key_takeaway="",
        )
        for a in articles
    ]


# ---------------------------------------------------------------------------
# Editorial intro
# ---------------------------------------------------------------------------

def generate_editorial_intro(summarized: list[SummarizedArticle]) -> str:
    """Generate a brief editorial intro paragraph for the digest."""
    categories: dict[str, list[str]] = {}
    for s in summarized:
        categories.setdefault(s.category, []).append(s.title)

    category_summary = "\n".join(
        f"- {cat}: {len(titles)} articles"
        for cat, titles in categories.items()
    )
    headlines = "\n".join(f"- {s.title}" for s in summarized[:5])

    prompt = (
        "Write a 2-3 sentence editorial intro for today's AI news digest.\n"
        f"Categories covered:\n{category_summary}\n\n"
        f"Top headlines:\n{headlines}\n\n"
        "Be concise, professional, forward-looking. "
        "No greetings. No fluff. Plain text only."
    )

    try:
        raw = _call_gemini_with_retry(prompt, _text_config(max_tokens=300))
        return raw.strip()
    except Exception as exc:
        logger.warning(f"Editorial intro generation failed: {exc}")
        return (
            "Today's AI digest covers the latest in edge computing, "
            "manufacturing AI, and broader industry developments."
        )


# ---------------------------------------------------------------------------
# Featured video selection
# ---------------------------------------------------------------------------

def pick_featured_video(
    videos: list[VideoCandidate],
) -> FeaturedVideo | None:
    """Ask Gemini to choose the single best educational video."""
    if not videos:
        return None

    videos_block = "\n".join(
        f"--- Video {i + 1} ---\n"
        f"Title: {v.title}\n"
        f"Channel: {v.channel_name}\n"
        f"URL: {v.url}\n"
        f"Published: {v.published.isoformat() if v.published else 'Unknown'}\n"
        f"Description: {v.description}\n"
        for i, v in enumerate(videos)
    )

    prompt = (
        "You are curating an educational video for a manufacturing engineering "
        "team that wants to learn about AI, edge computing, and Industry 4.0.\n\n"
        f"Below are {len(videos)} recent YouTube videos. Pick the SINGLE most "
        "educational and relevant video for this audience.\n\n"
        "Respond ONLY with JSON:\n"
        '{"index": <number starting from 1>, '
        '"reason": "<1 sentence, MAX 20 words — why valuable>", '
        '"description": "<2 sentences, MAX 30 words — what the viewer will learn>"}\n\n'
        f"Videos:\n{videos_block}"
    )

    try:
        raw = _call_gemini_with_retry(prompt, _json_config(max_tokens=500))
        data = _parse_json(raw)

        idx = data["index"] - 1
        if 0 <= idx < len(videos):
            v = videos[idx]
            return FeaturedVideo(
                title=v.title,
                url=v.url,
                channel_name=v.channel_name,
                thumbnail_url=v.thumbnail_url,
                description=data.get("description", ""),
                reason=data.get("reason", ""),
            )

        logger.warning(f"Gemini returned out-of-range video index: {data['index']}")
        return None

    except Exception as exc:
        logger.warning(f"Featured video selection failed: {exc}")
        return None
