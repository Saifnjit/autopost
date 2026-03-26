"""
Fetches relevant video clips from YouTube using yt-dlp.
Searches for official clips: company channels, press conferences,
product announcements, and viral news clips.
Falls back to Pexels if nothing found.
"""

import os
import subprocess
import json
import re


def build_search_query(article: dict) -> str:
    """Build a targeted YouTube search query from the article."""
    title = article.get("title", "")

    # Extract key names/companies using simple patterns
    companies = ["OpenAI", "Google", "Meta", "Microsoft", "Apple", "Amazon",
                 "Nvidia", "Tesla", "Anthropic", "xAI", "Mistral"]
    people = ["Sam Altman", "Elon Musk", "Sundar Pichai", "Mark Zuckerberg",
              "Satya Nadella", "Tim Cook", "Jensen Huang", "Dario Amodei"]

    found_people = [p for p in people if p.lower() in title.lower()]
    found_companies = [c for c in companies if c.lower() in title.lower()]

    # Build targeted query
    if found_people:
        return f"{found_people[0]} {found_companies[0] if found_companies else ''} 2024 2025 2026"
    elif found_companies:
        return f"{found_companies[0]} announcement news 2025 2026"
    else:
        # Generic search based on title keywords
        words = title.split()[:6]
        return " ".join(words) + " news"


def fetch_youtube_clip(article: dict, output_path: str = "news_clip.mp4", max_duration: int = 30) -> str | None:
    """
    Search YouTube and download the most relevant short clip.
    Prefers: official company channels, verified news, press conferences.
    """
    query = build_search_query(article)
    print(f"Searching YouTube for: '{query}'")

    try:
        # Search YouTube and get top results
        search_cmd = [
            "yt-dlp",
            f"ytsearch10:{query}",  # Get top 10 results
            "--dump-json",
            "--no-download",
            "--quiet",
            "--no-warnings",
        ]

        result = subprocess.run(search_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 or not result.stdout.strip():
            print("YouTube search returned no results")
            return None

        # Parse results and score them
        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                video = json.loads(line)
                score = score_video(video, article)
                videos.append((score, video))
            except Exception:
                continue

        if not videos:
            return None

        # Sort by score, pick best
        videos.sort(key=lambda x: x[0], reverse=True)
        best = videos[0][1]

        print(f"Best match: '{best.get('title', '')[:60]}' (score: {videos[0][0]})")

        # Download best clip (first 30 seconds only)
        download_cmd = [
            "yt-dlp",
            best["webpage_url"],
            "-o", output_path,
            "--format", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best",
            "--download-sections", f"*0-{max_duration}",
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            "--merge-output-format", "mp4",
        ]

        dl_result = subprocess.run(download_cmd, capture_output=True, text=True, timeout=60)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print(f"Downloaded YouTube clip: {output_path}")
            return output_path
        else:
            print(f"Download failed or file too small")
            return None

    except subprocess.TimeoutExpired:
        print("YouTube fetch timed out")
        return None
    except Exception as e:
        print(f"YouTube clip fetch error: {e}")
        return None


def score_video(video: dict, article: dict) -> int:
    """Score a YouTube video for relevance."""
    score = 0
    title = (video.get("title") or "").lower()
    channel = (video.get("channel") or video.get("uploader") or "").lower()
    duration = video.get("duration") or 999
    view_count = video.get("view_count") or 0
    article_title = (article.get("title") or "").lower()

    # Prefer shorter clips (more usable as b-roll)
    if duration <= 60:
        score += 5
    elif duration <= 180:
        score += 3
    elif duration <= 600:
        score += 1

    # Prefer official/verified channels
    official_channels = [
        "openai", "google", "meta", "microsoft", "tesla", "apple",
        "techcrunch", "the verge", "wired", "bloomberg", "cnbc",
        "cnn", "bbc", "reuters", "associated press", "ted",
        "nvidia", "anthropic", "ycombinator"
    ]
    if any(ch in channel for ch in official_channels):
        score += 8

    # Prefer recent videos (uploaded in last year)
    upload_date = video.get("upload_date") or ""
    if upload_date and upload_date[:4] in ["2025", "2026"]:
        score += 4
    elif upload_date and upload_date[:4] == "2024":
        score += 2

    # Keyword overlap with article
    article_words = set(article_title.split())
    title_words = set(title.split())
    overlap = len(article_words & title_words)
    score += overlap * 2

    # Penalize very long videos
    if duration > 3600:
        score -= 5

    # Prefer popular videos
    if view_count > 1000000:
        score += 3
    elif view_count > 100000:
        score += 2
    elif view_count > 10000:
        score += 1

    return score
