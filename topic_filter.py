"""
Filters articles to only pass real news stories with a specific subject.
Rejects discussions, questions, memes, and abstract observations.
"""

import anthropic
from config import ANTHROPIC_API_KEY
from settings import NICHE, NICHE_KEYWORDS

# Reject obvious non-news patterns before any API call
FAST_REJECT_STARTS = ("what ", "why ", "how ", "is ", "are ", "do ", "does ", "can ", "should ", "would ", "who ",
                      "managing ", "being ", "having ", "working ", "learning ", "building ", "using ")
FAST_REJECT_CONTAINS = ["meme", "joke", "funny", "lol", "wholesome", "cursed", "cringe", "unpopular opinion",
                        "discussion", "question", "eli5", "explain", "ask ", "thoughts on", "what do you think",
                        "humbles you", "changed my life", "lessons from", "things i learned", "my experience",
                        "first time", "as a ", "reminder that", "hot take"]

# Only fast-pass clear news signals — not just topic keywords
FAST_PASS_NEWS = ["raises", "raised", "acquires", "acquired", "launches", "launched", "releases", "released",
                  "announces", "announced", "ipo", "layoffs", "lays off", "shuts down", "shut down",
                  "billion", " million", "new model", "new product", "partnership", "merger", "banned",
                  "lawsuit", "fired", "hired", "steps down", "named ceo", "funding round", "series"]


def is_on_topic(article: dict) -> bool:
    """
    Returns True only if the article is:
    1. About AI/tech/business
    2. A real news story with a specific subject — not a discussion, question, or meme
    """
    title = (article.get("title") or "").strip()
    description = (article.get("description") or "").strip()

    if not title:
        return False

    title_lower = title.lower()
    combined = (title_lower + " " + description.lower())

    # Fast-reject obvious non-news
    if any(title_lower.startswith(s) for s in FAST_REJECT_STARTS):
        return False
    if any(kw in combined for kw in FAST_REJECT_CONTAINS):
        return False

    # Fast-pass if any niche keyword matches
    if any(kw in combined for kw in NICHE_KEYWORDS):
        if any(kw in combined for kw in FAST_PASS_NEWS):
            return True

    # Claude check for everything else — checks both topic AND news quality
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=5,
            timeout=15,
            messages=[{
                "role": "user",
                "content": (
                    f"Niche: {NICHE}\n\n"
                    f"Title: {title[:200]}\n"
                    f"Summary: {description[:300]}\n\n"
                    f"Is this a real news story (announcement, launch, funding, research, executive move, product release) "
                    f"directly relevant to the niche above? "
                    f"Reply only: yes or no"
                )
            }],
        )
        return message.content[0].text.strip().lower().startswith("yes")
    except Exception as e:
        print(f"  Topic filter error: {e} — rejecting article")
        return False
