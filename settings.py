"""
=====================================
  AutoPost — User Settings
  Edit this file to customize the bot
=====================================
"""

# ── What niche should the bot post about? ──────────────────────────────────────
# Examples: "fashion", "crypto", "fitness", "real estate", "AI and tech"
NICHE = "AI, tech startups, and the future of business"

# ── What tone/style should the captions be? ────────────────────────────────────
# Describe the voice you want. Be specific.
# Examples:
#   "Bold, trendy, and fashion-forward. Speak to Gen Z shoppers."
#   "Professional and data-driven. Speak to investors and founders."
#   "Casual and motivational. Speak to gym-goers and fitness enthusiasts."
POSTING_STYLE = (
    "Smart, direct, and a little dry. Like a founder texting a friend about "
    "something they just saw. Not a thought leader. Not a teenager. "
    "The person who always seems to know what's happening before everyone else."
)

# ── Which subreddits should the bot monitor? ───────────────────────────────────
# Find good ones at reddit.com/r/<name>
# Keep it to subreddits that are active and on-topic for your niche
SUBREDDITS = [
    "artificial",
    "singularity",
    "ChatGPT",
    "OpenAI",
    "MachineLearning",
    "technology",
    "startups",
    "Futurology",
]

# ── Keywords that instantly mark an article as on-topic ────────────────────────
# Add words that always mean "yes, this is relevant to my niche"
NICHE_KEYWORDS = [
    "ai", "artificial intelligence", "openai", "chatgpt", "gpt", "llm",
    "machine learning", "startup", "funding", "raises", "nvidia", "anthropic",
    "google", "microsoft", "meta", "apple", "automation", "robot", "tech",
]

# ── RSS feeds to monitor ────────────────────────────────────────────────────────
# Add any RSS feed URL that covers your niche
RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.wired.com/feed/rss",
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://www.technologyreview.com/feed/",
    "https://fortune.com/feed/",
]

# ── How many times per day should it post? ─────────────────────────────────────
# Times in 24hr format. Add or remove times as needed.
POST_TIMES = ["08:00", "13:00", "18:00"]

# ── Minimum viral score to post (1-10) ─────────────────────────────────────────
# Higher = stricter. 7 is recommended. Don't go below 6.
MIN_VIRAL_SCORE = 7
