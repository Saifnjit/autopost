"""
Fetches trending AI/tech content from:
- 8 core niche subreddits (top/week)
- Hacker News (top stories, 100+ upvotes)
- Twitter via Nitter
Sorted by engagement so the best content is checked first.
"""

import requests
import feedparser
import random
import time

HN_API = "https://hacker-news.firebaseio.com/v0"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

from settings import SUBREDDITS as CORE_SUBREDDITS, NICHE_KEYWORDS as HN_KEYWORDS, RSS_FEEDS as PRIMARY_RSS_FEEDS


def _extract_post(d: dict, subreddit: str) -> dict:
    """Convert raw Reddit post data to article dict."""
    reddit_images = []
    if d.get("is_gallery") and d.get("media_metadata"):
        for item in d["media_metadata"].values():
            try:
                reddit_images.append(item["s"]["u"].replace("&amp;", "&"))
            except Exception:
                pass
    preview_img = ""
    try:
        preview_img = d["preview"]["images"][0]["source"]["url"].replace("&amp;", "&")
    except Exception:
        pass
    direct_url = d.get("url", "")
    if not preview_img and direct_url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        preview_img = direct_url
    return {
        "title": d["title"],
        "description": d.get("selftext", "")[:400] or d["title"],
        "url": d.get("url", ""),
        "source": f"r/{subreddit}",
        "upvotes": d.get("ups", 0),
        "comments": d.get("num_comments", 0),
        "preview_image": preview_img,
        "reddit_images": reddit_images,
    }


def fetch_subreddit_top(subreddit: str, limit: int = 5) -> list[dict]:
    """Fetch top posts of the week from a subreddit — link posts only, no self/text posts."""
    try:
        r = requests.get(
            f"https://www.reddit.com/r/{subreddit}/top.json?t=week&limit=25",
            headers=HEADERS, timeout=10
        )
        posts = r.json()["data"]["children"]
        articles = []
        seen = set()
        for post in posts:
            d = post["data"]
            if d.get("stickied") or d.get("over_18") or d["title"] in seen:
                continue
            # Skip self/text posts — they have no external article or image
            if d.get("is_self"):
                continue
            # Skip posts that link back to Reddit itself
            url = d.get("url", "")
            if "reddit.com" in url or "redd.it" in url:
                continue
            seen.add(d["title"])
            articles.append(_extract_post(d, subreddit))
        articles.sort(key=lambda a: a["upvotes"] + a["comments"] * 3, reverse=True)
        return articles[:limit]
    except Exception as e:
        print(f"  r/{subreddit} error: {e}")
        return []


def fetch_hacker_news(limit: int = 15) -> list[dict]:
    """Fetch top Hacker News stories filtered for AI/tech relevance."""
    articles = []
    try:
        ids = requests.get(f"{HN_API}/topstories.json", timeout=8).json()[:50]
        for story_id in ids:
            if len(articles) >= limit:
                break
            try:
                d = requests.get(f"{HN_API}/item/{story_id}.json", timeout=5).json()
                if not d or d.get("type") != "story" or not d.get("title"):
                    continue
                if d.get("score", 0) < 100:
                    continue
                if not any(w in d["title"].lower() for w in HN_KEYWORDS):
                    continue
                # Skip HN discussion pages — no external article, no image
                story_url = d.get("url", "")
                if not story_url or "ycombinator.com" in story_url:
                    continue
                articles.append({
                    "title": d["title"],
                    "description": d.get("text", d["title"])[:400],
                    "url": story_url,
                    "source": "Hacker News",
                    "upvotes": d.get("score", 0),
                    "comments": d.get("descendants", 0),
                    "preview_image": "",
                    "reddit_images": [],
                })
            except Exception:
                continue
    except Exception as e:
        print(f"  HN error: {e}")
    articles.sort(key=lambda a: a["upvotes"] + a["comments"] * 2, reverse=True)
    print(f"  +{len(articles)} from Hacker News")
    return articles


def fetch_primary_rss() -> list[dict]:
    """Fetch from professional tech publications — always have clean, relevant images."""
    articles = []
    for feed_url in PRIMARY_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:8]:
                title = entry.get("title", "")
                url = entry.get("link", "")
                if not title or not url:
                    continue
                # Extract image from RSS entry if available
                preview_image = ""
                if hasattr(entry, "media_content") and entry.media_content:
                    preview_image = entry.media_content[0].get("url", "")
                elif hasattr(entry, "enclosures") and entry.enclosures:
                    for enc in entry.enclosures:
                        if enc.get("type", "").startswith("image"):
                            preview_image = enc.get("href", "")
                            break
                articles.append({
                    "title": title,
                    "description": entry.get("summary", "")[:400],
                    "url": url,
                    "source": feed.feed.get("title", "News"),
                    "upvotes": 500,  # Treat RSS articles as high engagement baseline
                    "comments": 0,
                    "preview_image": preview_image,
                    "reddit_images": [],
                })
        except Exception:
            continue
    print(f"  +{len(articles)} from RSS feeds")
    return articles


def fetch_candidate_articles(batch_size: int = 10, exclude_titles: set = None) -> list[dict]:
    """
    Returns a fresh batch of high-engagement AI/tech articles.
    Sources: 8 core subreddits + Hacker News + Twitter/Nitter.
    Sorted highest engagement first so viral checker hits best content immediately.
    """
    exclude_titles = exclude_titles or set()
    all_articles = []

    # Primary RSS feeds — professional publications with clean, relevant images
    print("Fetching primary RSS feeds...")
    all_articles += fetch_primary_rss()

    # Core subreddits — link posts only, no self/discussion posts
    print("Fetching top/week from core subreddits...")
    for subreddit in CORE_SUBREDDITS:
        posts = fetch_subreddit_top(subreddit, limit=3)
        all_articles += posts
        print(f"  r/{subreddit}: {len(posts)} posts")
        time.sleep(0.5)

    # Hacker News
    print("Fetching Hacker News...")
    all_articles += fetch_hacker_news(limit=10)

    # Deduplicate and remove already-tried
    seen = set()
    fresh = []
    for a in all_articles:
        if a["title"] not in seen and a["title"] not in exclude_titles:
            seen.add(a["title"])
            fresh.append(a)

    if not fresh:
        print("  No fresh candidates found")
        return []

    # Real news articles (with external URLs) first, then by engagement
    def _sort_key(a):
        url = a.get("url", "")
        has_real_url = int(bool(url) and "reddit.com" not in url and "ycombinator.com" not in url and "nitter." not in url)
        return (has_real_url, a.get("upvotes", 0) + a.get("comments", 0) * 3)
    fresh.sort(key=_sort_key, reverse=True)

    print(f"  {len(fresh)} fresh candidates — top: {fresh[0]['upvotes']} upvotes ({fresh[0]['title'][:50]})")
    return fresh[:batch_size * 2]


def fetch_trending_article() -> dict | None:
    articles = fetch_candidate_articles(batch_size=10)
    return articles[0] if articles else None
