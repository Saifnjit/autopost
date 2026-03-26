"""
Tracks posted content to prevent duplicates.
Saves post history to a local JSON file.
"""

import json
import os
from datetime import datetime, timedelta
from difflib import SequenceMatcher

HISTORY_FILE = "post_history.json"
MAX_HISTORY_DAYS = 7


def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history: list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"  History save error: {e}")


def clean_old_entries(history: list) -> list:
    cutoff = datetime.now() - timedelta(days=MAX_HISTORY_DAYS)
    clean = []
    for h in history:
        try:
            if datetime.fromisoformat(h["posted_at"]) > cutoff:
                clean.append(h)
        except Exception:
            pass  # Drop malformed entries
    return clean


def is_duplicate(article: dict, history: list, threshold: float = 0.6) -> bool:
    """Return True if this article is too similar to a recently posted one."""
    title = (article.get("title") or "").lower().strip()
    if not title:
        return False
    for entry in history:
        past_title = (entry.get("title") or "").lower().strip()
        if not past_title:
            continue
        if SequenceMatcher(None, title, past_title).ratio() >= threshold:
            return True
    return False


def record_post(article: dict, post_text: str):
    """Save a posted article to history."""
    history = clean_old_entries(load_history())
    history.append({
        "title": article.get("title", ""),
        "source": article.get("source", ""),
        "posted_at": datetime.now().isoformat(),
        "snippet": post_text[:100],
    })
    save_history(history)
    print(f"  Recorded to history ({len(history)} posts in last 7 days)")
