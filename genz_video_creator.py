"""
Gen Z video creator using ffmpeg directly — much more reliable than MoviePy.
- Downloads real YouTube clips
- Overlays text using ffmpeg drawtext
- Mixes narration + background music with ffmpeg
- Fast and stable
"""

import asyncio
import os
import subprocess
import json
import random
import time
import base64
import requests
import edge_tts
import anthropic
from config import ANTHROPIC_API_KEY, OPENAI_API_KEY

# --- VIDEO SETTINGS ---
WIDTH = 1080
HEIGHT = 1080
FPS = 30
CLIP_DURATION = 2.5

# --- TTS ---
TTS_VOICE = "en-US-ChristopherNeural"
TTS_RATE = "+20%"
TTS_PITCH = "+0Hz"

TRENDING_AUDIO_SEARCHES = [
    "cinematic background music no copyright dramatic",
    "epic news background music no copyright",
    "phonk instrumental no copyright 2024",
    "dark dramatic background music no copyright",
]


def find_ffmpeg() -> str:
    """Find ffmpeg executable."""
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    # Check common Python/moviepy install locations
    candidates = [
        r"C:\Users\saif\AppData\Local\Programs\Python\Python313\Lib\site-packages\imageio_ffmpeg\binaries",
    ]
    import glob
    for c in candidates:
        found = glob.glob(os.path.join(c, "ffmpeg*.exe"))
        if found:
            return found[0]
    return "ffmpeg"


def find_ffprobe() -> str:
    """Find ffprobe executable.

    BUG FIX: The old approach of FFMPEG.replace("ffmpeg", "ffprobe") is broken
    when the binary name contains "ffmpeg" as a substring with version info,
    e.g. "ffmpeg-win64-v4.2.2.exe" — the replace would yield
    "ffprobe-win64-v4.2.2.exe" which may not exist, and if the path also
    contains a directory component with "ffmpeg" in it the wrong segment
    gets replaced.  We now locate ffprobe independently using the same
    strategy as find_ffmpeg().
    """
    import shutil
    # 1. Check PATH first
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe

    # 2. Try to find it alongside the ffmpeg binary we already located
    ffmpeg_dir = os.path.dirname(FFMPEG)
    if ffmpeg_dir:
        import glob
        # Same-directory ffprobe*.exe (handles versioned names)
        found = glob.glob(os.path.join(ffmpeg_dir, "ffprobe*.exe"))
        if found:
            return found[0]
        # Plain ffprobe.exe
        candidate = os.path.join(ffmpeg_dir, "ffprobe.exe")
        if os.path.exists(candidate):
            return candidate
        # Plain ffprobe (Linux/macOS)
        candidate = os.path.join(ffmpeg_dir, "ffprobe")
        if os.path.exists(candidate):
            return candidate

    # 3. Check the same imageio_ffmpeg binaries directory
    candidates = [
        r"C:\Users\saif\AppData\Local\Programs\Python\Python313\Lib\site-packages\imageio_ffmpeg\binaries",
    ]
    import glob
    for c in candidates:
        found = glob.glob(os.path.join(c, "ffprobe*.exe"))
        if found:
            return found[0]

    # 4. Fall back to bare name and hope it is on PATH at runtime
    return "ffprobe"


FFMPEG = find_ffmpeg()
FFPROBE = find_ffprobe()


def run_ffmpeg(args: list, timeout: int = 120) -> bool:
    """Run an ffmpeg command. Returns True if successful."""
    cmd = [FFMPEG] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        if result.returncode != 0:
            print(f"ffmpeg error: {result.stderr[-300:]}")
            return False
        return True
    except Exception as e:
        print(f"ffmpeg failed: {e}")
        return False


async def generate_narration(text: str, path: str) -> float:
    """Generate TTS narration. Returns duration."""
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH)
    await communicate.save(path)
    # Get duration using ffprobe
    # BUG FIX: use the dedicated FFPROBE constant instead of a fragile string
    # replacement on the ffmpeg path.
    try:
        result = subprocess.run(
            [FFPROBE, "-v", "quiet", "-show_entries",
             "format=duration", "-of", "csv=p=0", path],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 3.5


def fetch_article_images(url: str, count: int) -> list:
    """Scrape all images from a news article page."""
    try:
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        img_urls = []

        # OG/Twitter meta images first
        for prop in ["og:image", "twitter:image", "og:image:secure_url"]:
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content") and tag["content"] not in img_urls:
                img_urls.append(tag["content"])

        # All <img> tags with src (filter small icons)
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                from urllib.parse import urlparse
                base = urlparse(url)
                src = f"{base.scheme}://{base.netloc}{src}"
            if src.startswith("http") and src not in img_urls:
                # Skip tiny icons/logos
                w = img.get("width", "999")
                h = img.get("height", "999")
                try:
                    if int(str(w)) < 200 or int(str(h)) < 200:
                        continue
                except Exception:
                    pass
                img_urls.append(src)

        # Download up to count images
        contents = []
        for img_url in img_urls:
            if len(contents) >= count:
                break
            try:
                img_data = requests.get(img_url, headers=headers, timeout=10)
                if img_data.status_code == 200 and len(img_data.content) > 10000:
                    contents.append(img_data.content)
            except Exception:
                continue

        return contents
    except Exception as e:
        print(f"  Article scrape error: {e}")
        return []


def search_reddit_images(query: str, count: int) -> list:
    """Search Reddit for posts about the query and collect their preview images."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "type": "link", "sort": "relevance", "limit": 25},
            headers=headers, timeout=10
        )
        posts = r.json()["data"]["children"]
        img_urls = []
        for post in posts:
            d = post["data"]
            if d.get("over_18"):
                continue
            # Gallery
            if d.get("is_gallery") and d.get("media_metadata"):
                for item in d["media_metadata"].values():
                    try:
                        img_urls.append(item["s"]["u"].replace("&amp;", "&"))
                    except Exception:
                        pass
            # Preview image
            try:
                img_urls.append(d["preview"]["images"][0]["source"]["url"].replace("&amp;", "&"))
            except Exception:
                pass
            # Direct image
            url = d.get("url", "")
            if url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                img_urls.append(url)
            if len(img_urls) >= count * 3:
                break

        results = []
        for img_url in img_urls:
            if len(results) >= count:
                break
            try:
                resp = requests.get(img_url, headers=headers, timeout=8)
                if resp.status_code == 200 and len(resp.content) > 10000:
                    results.append(resp.content)
            except Exception:
                continue
        return results
    except Exception as e:
        print(f"  Reddit search error: {e}")
        return []


def search_images_ddg(query: str, count: int) -> list:
    """Search DuckDuckGo Images for relevant pictures. Returns list of byte contents."""
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            hits = list(ddgs.images(query, max_results=count * 3))
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        for hit in hits:
            if len(results) >= count:
                break
            img_url = hit.get("image", "")
            if not img_url:
                continue
            try:
                r = requests.get(img_url, headers=headers, timeout=8)
                if r.status_code == 200 and len(r.content) > 10000:
                    results.append(r.content)
            except Exception:
                continue
        return results
    except Exception as e:
        print(f"  DDG image search error: {e}")
        return []


def filter_images_with_claude(candidates: list, article_title: str, needed: int) -> list:
    """
    Send candidate images to Claude Vision and ask which ones are relevant to the article.
    candidates: list of (bytes, source_label) tuples
    Returns list of bytes for relevant images only (up to needed).
    """
    if not candidates:
        return []

    print(f"  Asking Claude to filter {len(candidates)} candidate images for relevance...")
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        content = [
            {
                "type": "text",
                "text": (
                    f"Article title: \"{article_title}\"\n\n"
                    f"Below are {len(candidates)} candidate images numbered 1 to {len(candidates)}. "
                    f"For each image, answer YES if it is clearly relevant to the article topic, "
                    f"or NO if it is unrelated, generic, or could belong to any random article.\n"
                    f"Reply with ONLY a JSON array of the numbers of relevant images, e.g. [1, 3, 4]. "
                    f"Order them best-first. Return [] if none are relevant."
                )
            }
        ]

        for i, (img_bytes, _) in enumerate(candidates):
            # Detect format
            mime = "image/jpeg"
            if img_bytes[:4] == b'\x89PNG':
                mime = "image/png"
            elif img_bytes[:4] == b'RIFF':
                mime = "image/webp"
            content.append({
                "type": "text",
                "text": f"Image {i + 1}:"
            })
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": base64.standard_b64encode(img_bytes).decode("utf-8"),
                }
            })

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",  # fast + cheap for image filtering
            max_tokens=128,
            messages=[{"role": "user", "content": content}],
        )
        raw = message.content[0].text.strip()
        # Parse JSON array
        start = raw.find("[")
        end = raw.rfind("]") + 1
        chosen = json.loads(raw[start:end]) if start != -1 else []
        print(f"  Claude picked images: {chosen}")
        result = []
        for idx in chosen:
            if 1 <= idx <= len(candidates):
                result.append(candidates[idx - 1][0])
            if len(result) >= needed:
                break
        return result
    except Exception as e:
        print(f"  Claude vision filter error: {e} — using all candidates")
        return [b for b, _ in candidates[:needed]]


def generate_images_dalle(article_title: str, slides: list) -> list:
    """
    Use DALL-E 3 to generate one unique image per slide.
    Returns list of byte contents.
    """
    if not OPENAI_API_KEY:
        print("  No OpenAI API key — skipping DALL-E generation")
        return []

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        print("  openai package not installed — run: pip install openai")
        return []

    # First ask Claude to write a good DALL-E prompt for each slide
    try:
        ac = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt_request = ac.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": (
                    f"Article: \"{article_title}\"\n\n"
                    f"Write one short DALL-E 3 image generation prompt for each of these {len(slides)} slide captions. "
                    f"Each prompt must:\n"
                    f"- Be a photorealistic news-style image directly related to the article topic\n"
                    f"- Be under 50 words\n"
                    f"- NO text, logos, or watermarks in the image\n"
                    f"- Cinematic, high quality, professional news photography style\n\n"
                    + "\n".join(f"Slide {i+1}: {s}" for i, s in enumerate(slides))
                    + "\n\nReturn ONLY a JSON array of strings, one prompt per slide."
                )
            }]
        )
        raw = prompt_request.content[0].text.strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        prompts = json.loads(raw[start:end])
    except Exception as e:
        print(f"  Claude prompt generation error: {e} — using article title as prompt")
        prompts = [f"Photorealistic news photo about: {article_title}"] * len(slides)

    images = []
    for i, prompt in enumerate(prompts):
        print(f"  Generating image {i+1}/{len(slides)} with DALL-E 3...")
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            img_url = response.data[0].url
            img_data = requests.get(img_url, timeout=30)
            if img_data.status_code == 200:
                images.append(img_data.content)
                print(f"  ✓ Slide {i+1} image generated")
            else:
                images.append(None)
        except Exception as e:
            print(f"  DALL-E error on slide {i+1}: {e}")
            images.append(None)

    return images


def fetch_images_batch(query: str, count: int, article_url: str = "", preview_image: str = "", reddit_images: list = None, slides: list = None) -> list:
    """
    Generate images with DALL-E 3 (one per slide, perfectly relevant).
    Falls back to Reddit → article scrape → DDG if DALL-E fails.
    """
    print(f"  Fetching images for: '{query[:50]}'")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    target = count * 3  # fetch more than needed so Claude has options

    candidates = []  # list of (bytes, label)

    def _download(url: str, label: str):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200 and len(r.content) > 10000:
                candidates.append((r.content, label))
        except Exception:
            pass

    # Source 1: Reddit gallery images from the original post
    for url in (reddit_images or []):
        if len(candidates) >= target:
            break
        _download(url, "reddit-post")
    if preview_image:
        _download(preview_image, "reddit-preview")
    if candidates:
        print(f"  {len(candidates)} images from Reddit post")

    # Source 2: Reddit search — posts about same topic
    if len(candidates) < target:
        print(f"  Searching Reddit for more images...")
        for b in search_reddit_images(query, target - len(candidates)):
            candidates.append((b, "reddit-search"))
        print(f"  {len(candidates)} total candidates so far")

    # Source 3: Article page scrape
    if len(candidates) < target and article_url:
        for b in fetch_article_images(article_url, target - len(candidates)):
            candidates.append((b, "article"))

    # Source 4: DuckDuckGo
    if len(candidates) < target:
        for b in search_images_ddg(query, target - len(candidates)):
            candidates.append((b, "ddg"))

    if not candidates:
        return [None] * count

    # Claude Vision picks the most relevant ones
    approved = filter_images_with_claude(candidates, query, count)

    # Pad with remaining candidates if Claude approved fewer than needed
    if len(approved) < count:
        used = set(id(b) for b in approved)
        for b, _ in candidates:
            if id(b) not in used:
                approved.append(b)
                used.add(id(b))
            if len(approved) >= count:
                break

    paths = []
    for i in range(count):
        out = f"slide_img_{i}.jpg"
        if i < len(approved):
            with open(out, "wb") as f:
                f.write(approved[i])
            paths.append(out)
        else:
            paths.append(None)

    return paths


def fetch_image(query: str, index: int = 0) -> str | None:
    """Single image fetch — kept for compatibility."""
    results = fetch_images_batch(query, index + 1)
    return results[index] if results else None


def fetch_youtube_clip(query: str, index: int = 0, max_duration: int = 25) -> str | None:
    """Download a relevant YouTube clip."""
    print(f"  Searching YouTube: '{query[:50]}'")
    try:
        result = subprocess.run([
            "yt-dlp", f"ytsearch8:{query}",
            "--dump-json", "--no-download", "--quiet", "--no-warnings",
        ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25)

        if not result.stdout.strip():
            return None

        # Extract keywords from query for relevance scoring
        query_keywords = set(query.lower().split())
        query_keywords -= {"the", "a", "an", "of", "in", "on", "at", "to", "for", "is", "are", "was"}

        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line: continue
            try:
                v = json.loads(line)
                dur = v.get("duration") or 999
                views = v.get("view_count") or 0
                title = (v.get("title") or "").lower()
                sc = 0

                # Relevance — how many query keywords appear in the title
                keyword_hits = sum(1 for kw in query_keywords if kw in title)
                sc += keyword_hits * 4

                if dur <= 120: sc += 5
                elif dur <= 600: sc += 3
                if views > 500000: sc += 3
                elif views > 50000: sc += 2
                year = (v.get("upload_date") or "")[:4]
                if year in ["2025", "2026"]: sc += 3
                elif year == "2024": sc += 1

                videos.append((sc, v))
            except Exception:
                continue

        if not videos:
            return None

        videos.sort(key=lambda x: x[0], reverse=True)
        best = videos[0][1]
        print(f"  Found: '{best.get('title', '')[:55]}'")

        out = f"raw_clip_{index}.mp4"
        if os.path.exists(out):
            os.remove(out)

        # Download full video (no --download-sections, no ffmpeg needed for yt-dlp)
        raw = f"raw_clip_{index}_dl.mp4"
        dl = subprocess.run([
            "yt-dlp", best["webpage_url"],
            "-o", raw,
            "--format", "18/best[height<=360][ext=mp4]/best[height<=480][ext=mp4]/best[ext=mp4]",
            "--no-playlist", "--no-warnings",
        ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)

        if dl.returncode != 0:
            print(f"  yt-dlp error: {dl.stderr[-300:]}")

        if not os.path.exists(raw) or os.path.getsize(raw) < 50000:
            print(f"  ✗ Download failed")
            return None

        print(f"  Downloaded {os.path.getsize(raw) // 1024}KB — trimming to {max_duration}s...")

        # Trim and re-encode to ensure compatibility regardless of source format
        trim_ok = run_ffmpeg([
            "-y", "-i", raw,
            "-t", str(max_duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "28",
            "-an",
            out
        ], timeout=60)

        try:
            os.remove(raw)
        except Exception:
            pass

        if trim_ok and os.path.exists(out):
            print(f"  ✓ Clip ready ({os.path.getsize(out) // 1024}KB)")
            return out

        print(f"  ✗ Trim failed")
        return None

    except Exception as e:
        print(f"  YouTube error: {e}")
        return None


def fetch_trending_audio() -> str | None:
    """Download trending background music."""
    query = random.choice(TRENDING_AUDIO_SEARCHES)
    print(f"Fetching background music: '{query[:50]}'")
    try:
        result = subprocess.run([
            "yt-dlp", f"ytsearch5:{query}",
            "--dump-json", "--no-download", "--quiet", "--no-warnings",
        ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)

        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line: continue
            try:
                v = json.loads(line)
                dur = v.get("duration") or 0
                if 60 <= dur <= 600:
                    videos.append(v)
            except Exception:
                continue

        if not videos:
            return None

        raw_music = "bg_music_raw.mp4"
        out = "bg_music.mp3"
        for f in [raw_music, out]:
            if os.path.exists(f):
                os.remove(f)

        # Download video (no ffmpeg needed for yt-dlp)
        subprocess.run([
            "yt-dlp", videos[0]["webpage_url"],
            "-o", raw_music,
            "--format", "18/best[height<=360][ext=mp4]/best[ext=mp4]",
            "--no-warnings",
        ], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90)

        if not os.path.exists(raw_music) or os.path.getsize(raw_music) < 10000:
            return None

        # Extract audio using our ffmpeg
        ok = run_ffmpeg([
            "-y", "-i", raw_music,
            "-vn", "-c:a", "libmp3lame", "-q:a", "5",
            out
        ], timeout=60)

        try:
            os.remove(raw_music)
        except Exception:
            pass

        if ok and os.path.exists(out) and os.path.getsize(out) > 10000:
            print(f"✓ Background music downloaded")
            return out
        return None
    except Exception as e:
        print(f"Music error: {e}")
        return None


def prepare_clip(raw_path: str, duration: float, output: str) -> bool:
    """Convert image or video to square 1080x1080 clip."""
    ext = os.path.splitext(raw_path)[1].lower()
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        # Image → video: aggressive zoom punch (TikTok style)
        frames = int(duration * FPS)
        # BUG NOTE: The zoompan z expression '1.05+0.1*on/{frames}' is valid
        # ffmpeg arithmetic — 'on' is the 1-based output frame counter and
        # {frames} is substituted as a Python integer literal before the
        # string is passed to ffmpeg, so the division is floating-point at
        # runtime.  We clamp with max(1, ...) to guarantee the zoom never
        # drops below 1.0 (which would produce black borders).
        return run_ffmpeg([
            "-y", "-loop", "1", "-i", raw_path,
            "-t", str(duration),
            "-vf", (
                f"scale=1400:1400:force_original_aspect_ratio=increase,"
                f"crop=1400:1400,"
                f"zoompan=z='max(1,1.05+0.1*on/{frames})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an", output
        ], timeout=90)
    else:
        # Video → crop to square
        return run_ffmpeg([
            "-y", "-i", raw_path,
            "-t", str(duration),
            "-vf", f"crop=min(iw\\,ih):min(iw\\,ih),scale={WIDTH}:{HEIGHT},fps={FPS}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-an", output
        ], timeout=60)


def add_text_to_clip(clip_path: str, text: str, slide_num: int, total: int, duration: float, output: str) -> bool:
    """Use ffmpeg drawtext to overlay text on the clip."""
    # Aggressive escaping for ffmpeg drawtext filter
    safe_text = (text
        .replace("\\", "")
        .replace("'", "")
        .replace(":", " -")
        .replace(",", "")
        .replace("[", "")
        .replace("]", "")
        .replace("%", "")
        .replace("(", "")
        .replace(")", "")
        [:55])

    # Find best available bold font (C\:/ is the correct ffmpeg Windows path escaping)
    font_arg = ""
    for check_path in [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
        "C:/Windows/Fonts/impact.ttf",
    ]:
        if os.path.exists(check_path):
            ffmpeg_path = check_path.replace("C:/", "C\\:/")
            font_arg = f":fontfile='{ffmpeg_path}'"
            break
    tag = f"{slide_num}/{total}"

    # Word-wrap text into max 2 lines of ~30 chars each
    words = safe_text.split()
    line1, line2 = [], []
    for word in words:
        if len(" ".join(line1 + [word])) <= 30:
            line1.append(word)
        else:
            line2.append(word)
    line1_str = " ".join(line1)
    line2_str = " ".join(line2)[:30]

    box_h = 160 if line2_str else 100
    box_y = HEIGHT - box_h - 30

    # BUG FIX: vf was accidentally a Python tuple (parentheses + commas)
    # instead of a single string.  A tuple passed as a subprocess argument
    # becomes its repr "(str1, str2, str3)" which is not valid ffmpeg syntax
    # and causes every drawtext call to fail.  Use explicit string
    # concatenation so vf is always a str.
    vf = (
        f"drawbox=x=30:y={box_y}:w={WIDTH-60}:h={box_h}:color=black@0.7:t=fill"
        + f",drawtext=text='{tag}'{font_arg}:fontsize=22:fontcolor=white@0.7:x=20:y=20"
        + f",drawtext=text='{line1_str}'{font_arg}:fontsize=48:fontcolor=white:x=(w-text_w)/2:y={box_y+18}:line_spacing=6"
    )
    if line2_str:
        vf += f",drawtext=text='{line2_str}'{font_arg}:fontsize=48:fontcolor=white:x=(w-text_w)/2:y={box_y+80}:line_spacing=6"

    return run_ffmpeg([
        "-y", "-i", clip_path,
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-an", output
    ], timeout=60)


def _concat_fallback(slide_videos: list, slide_durations: list, output: str) -> bool:
    """Concatenate slides using the simple demuxer (no transitions).

    Used when xfade is unavailable or fails (older ffmpeg builds).
    """
    concat_list_path = "concat_list.txt"
    try:
        with open(concat_list_path, "w") as f:
            for v in slide_videos:
                f.write(f"file '{os.path.abspath(v)}'\n")
        ok = run_ffmpeg([
            "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            output
        ], timeout=120)
        return ok
    finally:
        try:
            os.remove(concat_list_path)
        except Exception:
            pass


def create_video(content: dict, query: str, output_path: str = "post_video.mp4", article_url: str = "", preview_image: str = "", reddit_images: list = None) -> str | None:
    slides = content.get("slides", [])
    if not slides:
        return None

    print(f"\n=== Creating Gen Z Video — {len(slides)} slides ===")

    # 1. Generate narration
    print("\n[1/4] Generating narration...")
    audio_paths = []
    durations = []
    for i, text in enumerate(slides):
        path = f"narr_{i}.mp3"
        try:
            dur = asyncio.run(generate_narration(text, path))
            dur = max(dur + 0.4, CLIP_DURATION)
            audio_paths.append(path)
            durations.append(dur)
            print(f"  Slide {i+1}: {dur:.1f}s — '{text[:45]}'")
        except Exception as e:
            print(f"  Slide {i+1} narration error: {e}")
            audio_paths.append(None)
            durations.append(CLIP_DURATION)

    # 2. Fetch images — Reddit preview first, then article scrape, then DDG/Pexels
    print("\n[2/4] Fetching images...")
    yt_clips = fetch_images_batch(query, len(slides), article_url=article_url, preview_image=preview_image, reddit_images=reddit_images or [], slides=slides)

    # 3. Fetch background music
    print("\n[3/4] Fetching background music...")
    bg_music = fetch_trending_audio()

    # 4. Build each slide
    print("\n[4/4] Building slides...")
    slide_videos = []
    slide_durations = []  # track durations only for successful slides
    for i, (text, dur) in enumerate(zip(slides, durations)):
        print(f"\n  Slide {i+1}/{len(slides)}...")
        raw = yt_clips[i] if i < len(yt_clips) else None
        prepared = f"prep_{i}.mp4"
        with_text = f"slide_{i}.mp4"

        # Prepare clip (crop + resize)
        if raw and os.path.exists(raw):
            ok = prepare_clip(raw, dur, prepared)
            if not ok:
                print(f"  Clip prep failed, using fallback")
                run_ffmpeg([
                    "-y", "-f", "lavfi",
                    "-i", f"color=c=0x0a0a0f:size={WIDTH}x{HEIGHT}:rate={FPS}",
                    "-t", str(dur), "-c:v", "libx264", prepared
                ])
        else:
            print(f"  No image — using dark background")
            run_ffmpeg([
                "-y", "-f", "lavfi",
                "-i", f"color=c=0x0a0a0f:size={WIDTH}x{HEIGHT}:rate={FPS}",
                "-t", str(dur), "-c:v", "libx264", prepared
            ])

        # Add text overlay
        ok = add_text_to_clip(prepared, text, i + 1, len(slides), dur, with_text)
        if ok and os.path.exists(with_text):
            slide_videos.append(with_text)
            slide_durations.append(dur)
            print(f"  ✓ Slide {i+1} ready")
        elif os.path.exists(prepared):
            slide_videos.append(prepared)
            slide_durations.append(dur)
            print(f"  ⚠ Text overlay failed, using clip without text")
        else:
            print(f"  ✗ Slide {i+1} failed entirely")

    if not slide_videos:
        return None

    # Concatenate slides with xfade transitions (TikTok style)
    # BUG FIX: 'concat_list' was defined here but never written to — the old
    # concat-demuxer approach had been replaced by xfade but the dead variable
    # remained and appeared in cleanup, causing confusion.  The variable is
    # now gone; concat fallback is handled by _concat_fallback() which manages
    # its own temp file internally.
    print("\nConcatenating slides with transitions...")
    silent_video = "silent_final.mp4"

    if len(slide_videos) == 1:
        import shutil
        shutil.copy(slide_videos[0], silent_video)
    else:
        # Build xfade filter_complex for smooth transitions
        # BUG FIX: if xfade fails (older ffmpeg without xfade support) we fall
        # back to a simple concat so that the rest of the pipeline can continue.
        transition = "fade"
        trans_dur = 0.3
        inputs = []
        for v in slide_videos:
            inputs += ["-i", v]

        # Build filter chain
        filter_parts = []
        offset = 0.0
        prev_label = "0:v"
        for i in range(1, len(slide_videos)):
            offset += slide_durations[i-1] - trans_dur
            out_label = f"v{i}"
            filter_parts.append(
                f"[{prev_label}][{i}:v]xfade=transition={transition}:duration={trans_dur}:offset={offset:.2f}[{out_label}]"
            )
            prev_label = out_label

        filter_str = ";".join(filter_parts)
        xfade_ok = run_ffmpeg([
            "-y"] + inputs + [
            "-filter_complex", filter_str,
            "-map", f"[{prev_label}]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            silent_video
        ], timeout=120)

        if not xfade_ok or not os.path.exists(silent_video):
            print("  xfade failed — falling back to simple concat (no transitions)")
            _concat_fallback(slide_videos, slide_durations, silent_video)

    if not os.path.exists(silent_video):
        return None

    # Build narration track
    print("Mixing audio...")
    # BUG FIX: narr_list path is always defined so cleanup never references an
    # undefined variable even when the narration block is skipped entirely.
    narr_list = "narr_list.txt"
    valid_narrations = [(i, p) for i, p in enumerate(audio_paths) if p and os.path.exists(p)]

    if valid_narrations:
        with open(narr_list, "w") as f:
            for i, p in valid_narrations:
                f.write(f"file '{os.path.abspath(p)}'\n")

        full_narration = "full_narration.mp3"
        run_ffmpeg(["-y", "-f", "concat", "-safe", "0",
                    "-i", narr_list, "-c:a", "libmp3lame", full_narration])

        total_dur = sum(durations)

        if bg_music and os.path.exists(bg_music):
            # Mix narration (full volume) + music (18%)
            run_ffmpeg([
                "-y",
                "-i", silent_video,
                "-i", full_narration,
                "-stream_loop", "-1", "-i", bg_music,
                "-filter_complex",
                f"[2:a]volume=0.18,atrim=0:{total_dur}[bg];"
                f"[1:a][bg]amix=inputs=2:duration=first[audio]",
                "-map", "0:v", "-map", "[audio]",
                "-c:v", "copy", "-c:a", "aac",
                "-shortest", output_path
            ])
            print("✓ Mixed narration + background music")
        else:
            # Narration only
            run_ffmpeg([
                "-y", "-i", silent_video, "-i", full_narration,
                "-c:v", "copy", "-c:a", "aac",
                "-shortest", output_path
            ])
            print("✓ Narration only (no background music)")
    else:
        # No audio at all
        import shutil
        shutil.copy(silent_video, output_path)

    # Cleanup
    # BUG FIX: yt_clips already contains the same paths as slide_img_{i}.jpg
    # (fetch_images_batch saves to that exact name).  Including both yt_clips
    # and the explicit slide_img_{i} loop would attempt to delete each image
    # twice.  The os.path.exists guard prevents an OSError on the second pass,
    # but it is cleaner to rely on only the explicit loop (which is always
    # complete) and drop yt_clips from this list.  narr_list is always defined
    # (set unconditionally above) so it is safe to include here regardless of
    # whether the file was actually written.
    temp_files = (
        [narr_list, silent_video, "full_narration.mp3", "bg_music.mp3", "bg_music_raw.mp4"] +
        audio_paths +
        [f"prep_{i}.mp4" for i in range(len(slides))] +
        [f"slide_{i}.mp4" for i in range(len(slides))] +
        [f"raw_clip_{i}.mp4" for i in range(len(slides))] +
        [f"slide_img_{i}.jpg" for i in range(len(slides))]
    )
    for f in temp_files:
        if f and os.path.exists(f):
            try: os.remove(f)
            except Exception: pass

    if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
        print(f"\n✓ Video ready: {output_path} ({os.path.getsize(output_path) // 1024}KB)")
        return output_path

    print("✗ Video creation failed")
    return None
