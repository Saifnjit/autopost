"""
MKBHD x TechCrunch style video with REAL footage:
- Pexels video clips (actual moving footage)
- Bold cinematic text overlay with slide-in animation
- AI narration (Edge TTS)
- Background music mixed under narration
- Dark cinematic color grade
- Blue accent branding
"""

import asyncio
import os
import textwrap
import requests
import random
import numpy as np
import edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from moviepy import VideoFileClip, VideoClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
from io import BytesIO

# --- VIDEO SETTINGS ---
WIDTH = 1080
HEIGHT = 1080
FPS = 30
CROSSFADE = 0.3
SECONDS_PER_SLIDE = 4.0  # fallback if audio shorter than this

# --- COLOR PALETTE (MKBHD style) ---
TEXT_COLOR = (255, 255, 255)
ACCENT_COLOR = (0, 120, 255)
DIM_COLOR = (150, 150, 160)
OVERLAY_ALPHA = 170

# --- TYPOGRAPHY ---
FONT_SIZE = 62

# --- TTS ---
TTS_VOICE = "en-US-GuyNeural"
TTS_RATE = "+12%"
TTS_PITCH = "-3Hz"

HEADERS = {"User-Agent": "Mozilla/5.0"}

MUSIC_URLS = [
    "https://cdn.pixabay.com/download/audio/2022/03/15/audio_8cb749a6b5.mp3",
    "https://cdn.pixabay.com/download/audio/2022/01/27/audio_d0c6ff1bab.mp3",
    "https://cdn.pixabay.com/download/audio/2021/11/13/audio_cb4f97b704.mp3",
]

# Search terms for dark cinematic footage — safe, professional
VIDEO_QUERIES = [
    "technology office",
    "artificial intelligence robot",
    "city skyline night",
    "data center servers",
    "business meeting professional",
    "futuristic technology",
    "coding programming",
    "stock market finance",
    "startup office team",
    "digital innovation",
]


def get_font(size: int, bold: bool = True):
    paths = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
    ]
    for path in paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def fetch_pexels_video(query: str, index: int = 0) -> str | None:
    """Download a Pexels video clip and return local path."""
    from config import PEXELS_API_KEY
    if not PEXELS_API_KEY:
        print("No Pexels API key found")
        return None

    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={
                "query": query,
                "orientation": "landscape",  # square not supported
                "per_page": 15,
            },
            timeout=15,
        )
        print(f"Pexels API status: {r.status_code} for query: '{query}'")
        if r.status_code != 200:
            print(f"Pexels error response: {r.text[:200]}")
            return None

        videos = r.json().get("videos", [])
        print(f"Pexels returned {len(videos)} videos")
        if not videos:
            return None

        video = videos[index % len(videos)]

        # Get best quality mp4
        mp4_url = None
        for f in sorted(video["video_files"], key=lambda x: x.get("width", 0), reverse=True):
            if f.get("type") == "video/mp4":
                mp4_url = f["link"]
                break

        if not mp4_url:
            return None

        path = f"clip_{index}.mp4"
        clip_r = requests.get(mp4_url, timeout=60, stream=True)
        with open(path, "wb") as fp:
            for chunk in clip_r.iter_content(chunk_size=8192):
                fp.write(chunk)

        print(f"Downloaded clip_{index}.mp4")
        return path

    except Exception as e:
        print(f"Pexels fetch error: {e}")
        return None


def fetch_unsplash_image(query: str) -> Image.Image | None:
    """Fallback: fetch a single image from Unsplash."""
    from config import UNSPLASH_ACCESS_KEY
    try:
        r = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": query, "orientation": "squarish", "content_filter": "high"},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        img_r = requests.get(data["urls"]["regular"], timeout=15)
        img = Image.open(BytesIO(img_r.content)).convert("RGB")
        img = ImageEnhance.Color(img).enhance(0.7)
        img = ImageEnhance.Brightness(img).enhance(0.65)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        return img.resize((WIDTH, HEIGHT), Image.LANCZOS)
    except Exception as e:
        print(f"Unsplash fallback error: {e}")
        return None


def add_text_overlay(frame_array: np.ndarray, text: str, slide_num: int, total: int, text_progress: float = 1.0) -> np.ndarray:
    """Add MKBHD-style text overlay to a video frame."""
    img = Image.fromarray(frame_array).convert("RGB")

    # Darken and desaturate
    img = ImageEnhance.Color(img).enhance(0.7)
    img = ImageEnhance.Brightness(img).enhance(0.65)
    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)

    # Dark gradient overlay
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    for y in range(HEIGHT):
        # Stronger at center-bottom
        alpha = int(180 * ((y / HEIGHT) ** 0.5))
        ov_draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    # Top accent bar
    draw.rectangle([0, 0, WIDTH, 7], fill=ACCENT_COLOR)

    # Slide counter
    counter_font = get_font(22, bold=False)
    draw.text((WIDTH - 65, 18), f"{slide_num}/{total}", font=counter_font, fill=DIM_COLOR)

    # Main text with slide-up animation
    font = get_font(FONT_SIZE)
    wrapped = textwrap.fill(text, width=22)
    lines = wrapped.split("\n")
    line_h = FONT_SIZE + 16
    total_h = len(lines) * line_h
    base_y = (HEIGHT - total_h) // 2 + 20
    offset = int((1.0 - min(text_progress * 2, 1.0)) * 70)
    y = base_y + offset

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        # Shadow layers
        for dx, dy in [(4, 4), (2, 2), (-1, -1)]:
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=TEXT_COLOR)
        y += line_h

    # Progress bar
    draw.rectangle([0, HEIGHT - 7, WIDTH, HEIGHT], fill=(20, 20, 30))
    draw.rectangle([0, HEIGHT - 7, int(WIDTH * slide_num / total), HEIGHT], fill=ACCENT_COLOR)

    return np.array(img)


def make_clip_from_video(video_path: str, text: str, duration: float, slide_num: int, total: int) -> VideoClip:
    """Create a clip from real Pexels footage with text overlay."""
    try:
        src = VideoFileClip(video_path).without_audio()

        # Crop to square
        if src.w > src.h:
            x_center = src.w / 2
            src = src.cropped(x_center=x_center, width=src.h)
        elif src.h > src.w:
            y_center = src.h / 2
            src = src.cropped(y_center=y_center, height=src.w)

        src = src.resized((WIDTH, HEIGHT))

        # Loop if shorter than needed
        if src.duration < duration:
            from moviepy import concatenate_videoclips as ccv
            loops = int(duration / src.duration) + 2
            src = ccv([src] * loops)

        src = src.subclipped(0, duration)

        # Apply text overlay using fl_image (efficient frame-by-frame)
        def apply_overlay(get_frame, t):
            frame = get_frame(t)
            progress = min(t / 0.4, 1.0)
            return add_text_overlay(frame, text, slide_num, total, progress)

        result = src.fl(apply_overlay)
        print(f"Slide {slide_num}: using real Pexels footage ✓")
        return result

    except Exception as e:
        print(f"Video clip error: {e}, using image fallback")
        return make_static_clip(text, duration, slide_num, total)


def make_static_clip(text: str, duration: float, slide_num: int, total: int) -> VideoClip:
    """Fallback: dark static background with text."""
    bg = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    bg[:, :] = [8, 8, 14]  # near-black

    def make_frame(t):
        progress = min(t / 0.4, 1.0)
        return add_text_overlay(bg.copy(), text, slide_num, total, progress)

    return VideoClip(make_frame, duration=duration)


def download_music() -> str | None:
    url = random.choice(MUSIC_URLS)
    path = "bg_music.mp3"
    try:
        r = requests.get(url, timeout=20)
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception as e:
        print(f"Music download failed: {e}")
        return None


async def generate_audio(text: str, path: str) -> float:
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH)
    await communicate.save(path)
    clip = AudioFileClip(path)
    dur = clip.duration
    clip.close()
    return dur


def create_video(content: dict, query: str, output_path: str = "post_video.mp4") -> str | None:
    slides = content.get("slides", [])
    if not slides:
        return None

    print(f"Creating video with {len(slides)} slides...")

    # Generate narration audio
    audio_paths = []
    durations = []
    for i, text in enumerate(slides):
        path = f"audio_{i}.mp3"
        try:
            dur = asyncio.run(generate_audio(text, path))
            dur = max(dur + 0.6, SECONDS_PER_SLIDE)
            audio_paths.append(path)
            durations.append(dur)
            print(f"Slide {i+1}: '{text[:45]}' ({dur:.1f}s)")
        except Exception as e:
            print(f"Audio error slide {i}: {e}")
            audio_paths.append(None)
            durations.append(SECONDS_PER_SLIDE)

    # Try YouTube first for slide 1, then Pexels for remaining slides
    video_clips_paths = []
    fallback_images = []

    # Slide 1: Try to get a relevant YouTube clip
    from clip_fetcher import fetch_youtube_clip
    yt_clip = fetch_youtube_clip({"title": query, "description": content.get("caption", "")}, output_path="yt_clip_0.mp4")
    video_clips_paths.append(yt_clip)
    fallback_images.append(None)

    # Remaining slides: use Pexels
    queries = [query] + VIDEO_QUERIES
    for i in range(1, len(slides)):
        q = queries[i % len(queries)]
        print(f"Fetching footage for slide {i+1}: '{q}'")
        path = fetch_pexels_video(q, index=i)
        video_clips_paths.append(path)
        if not path:
            img = fetch_unsplash_image(q)
            fallback_images.append(img)
        else:
            fallback_images.append(None)

    # Background music
    music_path = download_music()

    # Build clips
    clips = []
    for i, (text, dur) in enumerate(zip(slides, durations)):
        vid_path = video_clips_paths[i]
        if vid_path and os.path.exists(vid_path):
            clip = make_clip_from_video(vid_path, text, dur, i + 1, len(slides))
        elif fallback_images[i] is not None:
            # Use Unsplash image with Ken Burns effect
            img = fallback_images[i]
            n = int(dur * FPS)
            frames = []
            for j in range(n):
                t = j / max(n - 1, 1)
                scale = 1.0 + 0.06 * t
                nw, nh = int(WIDTH * scale), int(HEIGHT * scale)
                zoomed = img.resize((nw, nh), Image.LANCZOS)
                x0, y0 = (nw - WIDTH) // 2, (nh - HEIGHT) // 2
                cropped = zoomed.crop((x0, y0, x0 + WIDTH, y0 + HEIGHT))
                progress = min(t / 0.35, 1.0)
                frames.append(add_text_overlay(np.array(cropped), text, i + 1, len(slides), progress))
            clip = VideoClip(lambda t, f=frames: f[min(int(t * FPS), len(f) - 1)], duration=dur)
        else:
            clip = make_static_clip(text, dur, i + 1, len(slides))

        # Attach narration + music
        if audio_paths[i] and os.path.exists(audio_paths[i]):
            try:
                narration = AudioFileClip(audio_paths[i])
                if music_path and os.path.exists(music_path):
                    try:
                        start = sum(durations[:i])
                        bg = AudioFileClip(music_path).with_volume_scaled(0.09)
                        if bg.duration >= start + dur:
                            bg = bg.subclipped(start, start + dur)
                        else:
                            bg = bg.subclipped(0, min(dur, bg.duration))
                        mixed = CompositeAudioClip([narration, bg])
                        clip = clip.with_audio(mixed)
                    except Exception:
                        clip = clip.with_audio(narration)
                else:
                    clip = clip.with_audio(narration)
            except Exception as e:
                print(f"Audio attach error: {e}")

        clips.append(clip)

    if not clips:
        return None

    print("Rendering final video...")
    final = concatenate_videoclips(clips, method="compose", padding=-CROSSFADE)
    final.write_videofile(
        output_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        logger=None,
        threads=4,
    )

    # Cleanup
    for p in audio_paths:
        if p and os.path.exists(p):
            os.remove(p)
    for p in video_clips_paths:
        if p and os.path.exists(p):
            os.remove(p)
    if music_path and os.path.exists(music_path):
        os.remove(music_path)

    print(f"Video done: {output_path}")
    return output_path
