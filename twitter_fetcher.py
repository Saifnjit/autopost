"""
Scrapes trending tweets from Nitter (Twitter mirror — no API needed).
Extracts tweet text + attached images for the LinkedIn bot pipeline.
"""

import requests
import feedparser
import random
import re
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.net",
    "https://nitter.cz",
]

SEARCH_QUERIES = [
    "artificial intelligence",
    "OpenAI",
    "AI startup funding",
    "tech layoffs",
    "AI business",
    "machine learning breakthrough",
    "GPT Claude Gemini",
    "startup raises million",
]


def _get_working_instance() -> str | None:
    """Find a Nitter instance that is currently up."""
    for instance in NITTER_INSTANCES:
        try:
            r = requests.get(instance, headers=HEADERS, timeout=6)
            if r.status_code == 200:
                return instance
        except Exception:
            continue
    return None


def _parse_tweet_html(description_html: str, instance: str) -> tuple[str, list[str]]:
    """Extract clean text and image URLs from Nitter RSS description HTML."""
    soup = BeautifulSoup(description_html, "html.parser")

    # Fix operator precedence: all three conditions require src to be non-empty
    img_urls = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src and ("pic" in src or "media" in src or "twimg" in src):
            if src.startswith("/"):
                src = instance + src
            img_urls.append(src)

    text = soup.get_text(" ", strip=True)
    text = re.sub(r"^RT @\w+:\s*", "", text)
    text = re.sub(r"http\S+", "", text).strip()

    return text, img_urls


def fetch_nitter_search(query: str, instance: str, limit: int = 15) -> list[dict]:
    """Search Nitter RSS for tweets about a query."""
    tweets = []
    try:
        feed_url = f"{instance}/search/rss?q={requests.utils.quote(query)}&f=tweets"
        feed = feedparser.parse(feed_url, request_headers=HEADERS)

        if not feed.entries:
            print(f"    No entries from {instance} for '{query}'")
            return []

        for entry in feed.entries[:limit]:
            title = entry.get("title", "")
            description = entry.get("description", entry.get("summary", ""))
            text, img_urls = _parse_tweet_html(description, instance)

            if not text or len(text) < 20:
                continue

            tweets.append({
                "title": title[:150],
                "description": text[:400],
                "url": entry.get("link", ""),
                "source": "Twitter",
                "upvotes": 0,
                "comments": 0,
                "preview_image": img_urls[0] if img_urls else "",
                "reddit_images": img_urls,
            })
    except Exception as e:
        print(f"  Nitter search error ({instance}, '{query}'): {e}")
    return tweets


def fetch_twitter_articles(limit: int = 20) -> list[dict]:
    """
    Returns tweet-based articles with images.
    Tries multiple Nitter instances and search queries.
    Prioritises tweets that have images.
    """
    print("  Finding working Nitter instance...")
    instance = _get_working_instance()
    if not instance:
        print("  No Nitter instance available")
        return []

    print(f"  Using: {instance}")
    all_tweets = []

    queries = random.sample(SEARCH_QUERIES, min(4, len(SEARCH_QUERIES)))
    for query in queries:
        if not query.strip():
            continue
        results = fetch_nitter_search(query, instance, limit=8)
        all_tweets += results
        if results:
            print(f"  +{len(results)} tweets for '{query}'")

    # Deduplicate by title
    seen = set()
    unique = []
    for t in all_tweets:
        if t["title"] and t["title"] not in seen:
            seen.add(t["title"])
            unique.append(t)

    # Tweets with images first
    with_images = [t for t in unique if t["preview_image"]]
    without_images = [t for t in unique if not t["preview_image"]]

    combined = with_images + without_images
    print(f"  {len(combined)} tweets ({len(with_images)} with images)")
    return combined[:limit]
