"""
Fetches the most relevant image for a LinkedIn post.
Pipeline:
1. Extract main subject (person/company) from article title
2. Wikipedia headshot → article og:image → Bing Images → Reddit
3. Claude Vision picks the most relevant image
"""

import base64
import json as json_lib
import requests
import anthropic
from bs4 import BeautifulSoup
from config import ANTHROPIC_API_KEY

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _download(url: str) -> bytes | None:
    """Download image — requires at least 10KB (article/Reddit images are full size)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and len(r.content) > 10000:
            return r.content
    except Exception:
        pass
    return None


def _download_small(url: str) -> bytes | None:
    """Download image with lower threshold — Bing thumbnails are legitimately small (3–8KB)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and len(r.content) > 2000:
            return r.content
    except Exception:
        pass
    return None


def _extract_subject(title: str) -> str:
    """
    Use Claude Haiku to pull the main person or company name out of an article title.
    e.g. 'Peter Thiel's Founders Fund raises $4.6B' → 'Peter Thiel'
    Falls back to full title on error.
    """
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            timeout=15,
            messages=[{"role": "user", "content": (
                f"Extract the most specific searchable subject from this headline for an image search. "
                f"Prefer a person's name over a company or institution. "
                f"If no person, use the company or product name. "
                f"Never return a university or generic institution — return the topic or person instead. "
                f"Reply with just the name or topic, nothing else.\n\nHeadline: {title}"
            )}],
        )
        subject = msg.content[0].text.strip().strip('"\'')
        return subject if len(subject) > 2 else title
    except Exception:
        return title


def _search_wikipedia_image(subject: str) -> bytes | None:
    """
    Fetch the full-resolution Wikipedia image for a well-known person or company.
    Prefers originalimage (full res) over thumbnail (320px).
    """
    try:
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(subject)}",
            headers=HEADERS, timeout=8,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        # originalimage first — full resolution, not the 320px thumbnail
        img_url = (
            data.get("originalimage", {}).get("source")
            or data.get("thumbnail", {}).get("source")
        )
        if not img_url:
            return None
        return _download(img_url)
    except Exception:
        return None


def _search_bing_images(query: str, count: int = 5) -> list[bytes]:
    """
    Search Bing Images and extract full-size source URLs from the JSON metadata
    embedded in each result (murl field) — not the blurry Bing thumbnails.
    """
    results = []
    try:
        search_url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&form=HDRSC2"
        r = requests.get(search_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html",
        }, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # Each Bing image result has an <a class="iusc"> with a JSON "m" attribute
        # containing "murl" — the original full-size image URL
        for a in soup.select("a.iusc"):
            m = a.get("m", "")
            if not m:
                continue
            try:
                data = json_lib.loads(m)
                src = data.get("murl", "")
                if not src or not src.startswith("http"):
                    continue
                b = _download(src)
                if b:
                    results.append(b)
                if len(results) >= count:
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"  Bing image search error: {e}")
    return results


def _get_article_og_image(url: str) -> bytes | None:
    """Fetch only the og:image / twitter:image meta tag from an article page."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for prop in ["og:image", "twitter:image", "og:image:secure_url"]:
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                b = _download(tag["content"])
                if b:
                    return b
    except Exception as e:
        print(f"  Article og:image error: {e}")
    return None


def _collect_candidates(article: dict) -> list:
    """
    Collect image candidates in priority order:
    1. Wikipedia headshot (most specific — actual photo of the person/company)
    2. Article og:image (news articles only — not Reddit/HN/Twitter)
    3. Bing image search on the extracted subject name

    Reddit post images are intentionally excluded — they are user-uploaded
    memes, screenshots, and random content that are almost never relevant.
    """
    candidates = []
    article_url = article.get("url", "")
    title = (article.get("title") or "").strip()

    # Extract the main subject for targeted searches (person or company name)
    subject = ""
    if title:
        subject = _extract_subject(title)
        if subject and subject != title:
            print(f"  Subject extracted: '{subject}'")
        elif not subject:
            subject = title

    # 1. Wikipedia headshot — only useful for individual people and specific companies
    # Skip universities, generic institutions — their Wikipedia image is always a building
    _skip_wiki = ("university", "institute", "college", "school", "mit", "stanford", "harvard",
                  "oxford", "cambridge", "department", "foundation", "committee", "government")
    if subject and not any(s in subject.lower() for s in _skip_wiki):
        print(f"  Searching Wikipedia for: '{subject}'")
        wiki_img = _search_wikipedia_image(subject)
        if wiki_img:
            candidates.append(wiki_img)
            print(f"  ✓ Wikipedia image found")

    # 2. Article og:image — the publication's chosen photo for the story
    # Skip Reddit/HN/Twitter URLs — their og:image is just a site logo, not relevant
    _skip_og = ("reddit.com", "redd.it", "news.ycombinator.com", "nitter.", "twitter.com", "x.com")
    if article_url and not any(s in article_url for s in _skip_og):
        print(f"  Fetching article og:image...")
        og = _get_article_og_image(article_url)
        if og:
            candidates.append(og)
            print(f"  ✓ Article og:image found")

    # 3. Bing image search — always run
    if subject:
        print(f"  Searching Bing Images for: '{subject}'")
        bing_imgs = _search_bing_images(subject, count=5)
        candidates += bing_imgs
        if bing_imgs:
            print(f"  ✓ {len(bing_imgs)} images from Bing")

    return candidates


def _claude_pick_and_validate(candidates: list, article_title: str, caption: str) -> bytes | None:
    """
    Claude Vision picks the best image from the candidates.
    Returns None if no suitable image found or on error.
    """
    if not candidates:
        return None

    print(f"  Asking Claude to pick best image from {len(candidates)} candidates...")
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        content = [{
            "type": "text",
            "text": (
                f"Article topic: \"{article_title}\"\n"
                f"Caption: \"{caption[:200]}\"\n\n"
                f"Pick the image that directly represents this story's subject. "
                f"ONLY accept: the actual person named, the company logo, the product shown, "
                f"or a graphic/screenshot explicitly about this story. "
                f"REJECT and reply 0 for: security cameras, random rooms, cartoons, memes, "
                f"animals, food, crowds, buildings, or anything not directly tied to the story. "
                f"If you are not confident the image matches, reply 0. "
                f"Reply with ONLY a single number (1 to {len(candidates)}) or 0."
            )
        }]
        for i, img_bytes in enumerate(candidates):
            mime = "image/png" if img_bytes[:4] == b'\x89PNG' else "image/jpeg"
            content.append({"type": "text", "text": f"Image {i+1}:"})
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": base64.standard_b64encode(img_bytes).decode("utf-8"),
                }
            })

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            timeout=60,
            messages=[{"role": "user", "content": content}],
        )
        raw = "".join(c for c in msg.content[0].text.strip() if c.isdigit())
        pick = int(raw) if raw else 0
        if pick == 0:
            print("  Claude: no suitable image found")
            return None
        pick = max(1, min(pick, len(candidates)))
        print(f"  Claude picked image {pick}")
        return candidates[pick - 1]
    except Exception as e:
        print(f"  Claude pick error: {e}")
        return None  # Don't risk posting an irrelevant image


def fetch_best_image(article: dict, caption: str, output_path: str = "post_image.jpg") -> str | None:
    """
    Fetch the best image for the article and validate it fits the caption.
    Returns file path or None.
    """
    print("\n[Image] Collecting candidates...")
    candidates = _collect_candidates(article)
    print(f"  {len(candidates)} candidates found — sizes: {[len(b)//1024 for b in candidates]}KB")

    if not candidates:
        print("  No images found")
        return None

    best = _claude_pick_and_validate(candidates, article.get("title", ""), caption)
    if not best:
        print("  No suitable image found")
        return None

    with open(output_path, "wb") as f:
        f.write(best)
    print(f"  ✓ Image saved ({len(best) // 1024}KB)")
    return output_path
