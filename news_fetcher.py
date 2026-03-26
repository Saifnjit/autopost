import requests
import random
import feedparser
from datetime import datetime, timedelta

# Reddit subreddits — only high-signal, niche-relevant ones
SUBREDDITS = [
    "artificial",
    "ChatGPT",
    "MachineLearning",
    "OpenAI",
    "startups",
    "entrepreneur",
    "tech",
    "singularity",
    "technology",
    "business",
    "Futurology",
    "programming",
]

# RSS feeds — only tech/business/AI publications
RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://www.wired.com/feed/rss",
    "https://feeds.arstechnica.com/arstechnica/index",
]

# Keywords that signal viral/high-engagement potential
VIRAL_KEYWORDS = [
    "billion", "million", "record", "first ever", "breakthrough",
    "disrupts", "shuts down", "raises", "acquires", "beats",
    "surpasses", "warns", "predicts", "reveals", "launches",
    "fired", "resigns", "banned", "leaked", "exclusive",
    "breaking", "massive", "shocking", "ai", "gpt", "openai",
    "anthropic", "google", "meta", "microsoft", "startup",
]

# Must contain at least one of these to be accepted
REQUIRED_TOPICS = [
    "ai", "artificial intelligence", "gpt", "openai", "claude", "gemini",
    "startup", "founder", "funding", "venture", "tech", "software",
    "business", "entrepreneur", "strategy", "innovation", "automation",
    "robot", "machine learning", "data", "saas", "microsoft", "google",
    "meta", "apple", "amazon", "nvidia", "leadership", "productivity",
]

# Reject articles containing these — off-topic noise
BLACKLIST_KEYWORDS = [
    "sale", "discount", "coupon", "weather", "sports", "nfl", "nba",
    "recipe", "fashion", "celebrity", "movie", "music", "travel",
    "real estate", "property", "mortgage", "gardening", "cooking",
    "makeup", "skincare", "fitness", "diet", "weight loss",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LinkedInBot/1.0)"}


def fetch_from_reddit() -> list[dict]:
    """Fetch top trending posts from relevant subreddits."""
    articles = []
    subreddit = random.choice(SUBREDDITS)

    try:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=20"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        posts = response.json()["data"]["children"]

        for post in posts:
            data = post["data"]
            # Skip stickied posts, self-posts with no content, NSFW
            if data.get("stickied") or data.get("over_18"):
                continue

            articles.append({
                "title": data["title"],
                "description": data.get("selftext", "")[:300] or data["title"],
                "url": data.get("url", ""),
                "source": f"r/{subreddit}",
                "upvotes": data.get("ups", 0),
                "comments": data.get("num_comments", 0),
                "query": subreddit,
            })
    except Exception as e:
        print(f"Reddit fetch error: {e}")

    return articles


def fetch_from_rss() -> list[dict]:
    """Fetch latest articles from RSS feeds."""
    articles = []
    feed_url = random.choice(RSS_FEEDS)

    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:10]:
            articles.append({
                "title": entry.get("title", ""),
                "description": entry.get("summary", "")[:300],
                "url": entry.get("link", ""),
                "source": feed.feed.get("title", "News"),
                "upvotes": 0,
                "comments": 0,
                "query": feed.feed.get("title", "news"),
            })
    except Exception as e:
        print(f"RSS fetch error: {e}")

    return articles


def is_relevant(article: dict) -> bool:
    """Return True only if article is on-topic and not blacklisted."""
    text = ((article.get("title") or "") + " " + (article.get("description") or "")).lower()

    # Reject if blacklisted
    if any(word in text for word in BLACKLIST_KEYWORDS):
        return False

    # Must match at least one required topic
    return any(topic in text for topic in REQUIRED_TOPICS)


def score_article(article: dict) -> int:
    """Score an article based on viral potential."""
    score = 0
    title = (article.get("title") or "").lower()
    description = (article.get("description") or "").lower()
    text = title + " " + description

    # Reddit engagement signals
    upvotes = article.get("upvotes", 0)
    comments = article.get("comments", 0)
    if upvotes > 10000:
        score += 10
    elif upvotes > 5000:
        score += 7
    elif upvotes > 1000:
        score += 4
    elif upvotes > 100:
        score += 2

    if comments > 500:
        score += 5
    elif comments > 100:
        score += 3

    # Viral keywords
    for keyword in VIRAL_KEYWORDS:
        if keyword in text:
            score += 2

    # Penalise missing content
    if not article.get("title") or not article.get("description"):
        score -= 10

    return score


def fetch_trending_article() -> dict | None:
    """Fetch the most viral trending article from Reddit or RSS."""
    # 70% chance Reddit, 30% chance RSS (Reddit = better trending signal)
    if random.random() < 0.7:
        articles = fetch_from_reddit()
        if not articles:
            articles = fetch_from_rss()
    else:
        articles = fetch_from_rss()
        if not articles:
            articles = fetch_from_reddit()

    if not articles:
        return None

    # Filter to only relevant articles
    relevant = [a for a in articles if is_relevant(a)]

    if not relevant:
        print("No relevant articles found this cycle, trying RSS fallback...")
        fallback = fetch_from_rss()
        relevant = [a for a in fallback if is_relevant(a)]

    if not relevant:
        return None

    # Score and pick the best
    scored = sorted(relevant, key=score_article, reverse=True)
    best = scored[0]

    if not best.get("title"):
        return None

    return best
