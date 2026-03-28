# AutoPost — AI LinkedIn Bot

> Automatically finds trending news, writes viral LinkedIn posts with Claude AI, and publishes them 3× daily. Zero effort after setup.

**Live demo:** [saifnjit.github.io/autopost](https://saifnjit.github.io/autopost)

---

## What it does

AutoPost runs in the background and posts to your LinkedIn automatically:

1. Scans Reddit, Hacker News, TechCrunch, Wired, The Verge and more for trending stories in your niche
2. Filters out discussions, memes, and low-quality content
3. Writes a hook-first LinkedIn post grounded in real facts using Claude Sonnet
4. Scores every post for viral potential (hook strength, emotion, specificity, CTA) — anything below 7/10 is skipped
5. Finds a relevant image using Wikipedia, article og:image, or Bing — validated by Claude Vision
6. Posts to LinkedIn via the official API at 8am, 1pm, and 6pm

---

## Demo

![Landing Page](docs/de21dd2a-b196-42bf-b7ad-ef733247ae63.jpg)

| Live LinkedIn Post | Desktop App — Bot Running |
|---|---|
| ![Post](docs/999ad134-4bdd-49bb-9db7-926169be9fbb.jpg) | ![Dashboard](docs/Screenshot%202026-03-27%20225238.png) |

---

## Architecture

```
main.py
├── trending_fetcher.py     # RSS feeds + Reddit + Hacker News
├── topic_filter.py         # Fast-reject + Claude Haiku niche filter
├── content_generator.py    # Claude Sonnet writes the post
├── viral_checker.py        # Scores post 1–10, skips below threshold
├── image_fetcher.py        # Wikipedia → og:image → Bing + Claude Vision validation
└── linkedin_poster.py      # Posts via LinkedIn API v2

settings.py                 # User config: niche, style, times, subreddits
app.py                      # CustomTkinter desktop GUI (optional)
```

---

## Tech Stack

- **Python 3.11**
- **Claude API** (Anthropic) — Sonnet for writing, Haiku for filtering, Haiku Vision for image validation
- **LinkedIn API v2** — official posting endpoint
- **Reddit JSON API** — no auth required for public posts
- **RSS / feedparser** — TechCrunch, Wired, The Verge, VentureBeat, Ars Technica
- **Wikipedia REST API** — person/company headshots
- **BeautifulSoup4** — og:image scraping
- **APScheduler** — 3× daily scheduling
- **CustomTkinter** — desktop GUI

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/Saifnjit/autopost
cd autopost
pip install -r requirements.txt
```

### 2. Add your keys

```bash
cp .env.example .env
```

Edit `.env`:

```
LINKEDIN_ACCESS_TOKEN=your_token_here
ANTHROPIC_API_KEY=sk-ant-...
```

**LinkedIn token** — create an app at [linkedin.com/developers](https://www.linkedin.com/developers/apps) with `w_member_social` scope

**Anthropic key** — get one at [console.anthropic.com](https://console.anthropic.com)

### 3. Configure your niche

Edit `settings.py`:

```python
NICHE = "AI, tech startups, and the future of business"
POSTING_STYLE = "Smart, direct, and a little dry. Like a founder texting a friend."
POST_TIMES = ["08:00", "13:00", "18:00"]
MIN_VIRAL_SCORE = 7
```

### 4. Run

```bash
python main.py
```

Or open the desktop app:

```bash
python app.py
```

---

## How the viral filter works

Every generated post is scored across 5 criteria:

| Criterion | What it checks |
|---|---|
| Hook | Does line 1 stop the scroll? |
| Emotion | Fear, awe, curiosity, or urgency present? |
| Specificity | Real facts, numbers, names — not vague observations |
| Conflict | Bold claim that sparks disagreement |
| CTA | Does it trigger identity-based comments? |

Posts scoring below 7/10 are discarded and the pipeline retries with a new article.

---

## How the image pipeline works

1. Extract subject (person or company) from headline using Claude Haiku
2. Search Wikipedia for a high-res headshot (`originalimage`, not thumbnail)
3. Skip Wikipedia for institutions (returns building photos)
4. Scrape og:image from the article
5. Search Bing for full-size images via `a.iusc` JSON
6. Pass all candidates to Claude Haiku Vision — pick the most relevant, reject generics
7. If nothing passes, skip the post (no text-only posts)

---

## Project structure

```
autopost/
├── main.py                 # Entry point + scheduler
├── settings.py             # User config
├── config.py               # Internal config + brand voice
├── trending_fetcher.py     # Content sources
├── topic_filter.py         # Niche relevance filter
├── content_generator.py    # Post writing
├── viral_checker.py        # Viral scoring
├── image_fetcher.py        # Image sourcing + validation
├── linkedin_poster.py      # LinkedIn API
├── post_history.py         # Duplicate prevention (7-day window)
├── app.py                  # Desktop GUI
├── docs/                   # Landing page (GitHub Pages)
│   ├── index.html
│   └── setup.html
└── requirements.txt
```

---

## Built by

**Saif** — [LinkedIn](https://linkedin.com) · [GitHub](https://github.com/Saifnjit)

Built with Claude AI · MIT License
