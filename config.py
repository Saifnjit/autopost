import os
from dotenv import load_dotenv

load_dotenv()

LINKEDIN_ACCESS_TOKEN = (os.getenv("LINKEDIN_ACCESS_TOKEN") or "").strip()
ANTHROPIC_API_KEY = (os.getenv("ANTHROPIC_API_KEY") or "").strip()

# Load user settings
from settings import POST_TIMES, POSTING_STYLE, MIN_VIRAL_SCORE  # noqa: E402

BRAND_VOICE = f"""
You are writing LinkedIn posts in this style: {POSTING_STYLE}

What works:
- Observations that make someone go "huh, I hadn't thought of it that way"
- Dry understatement over hype ("quietly a big deal", "this aged poorly", "turns out X was right")
- Specific details over vague claims — names, numbers, real examples
- Natural lowercase rhythm when it flows, not forced
- Short paragraphs. mobile first. lots of white space.

What to avoid:
- Hustle culture clichés ("grind", "level up", "this changed everything")
- Fake Gen Z slang ("no cap", "bro", "slay", "based") — sounds like an ad trying to be cool
- Thought leader energy ("I've been thinking a lot about...", "Here's what most people miss:")
- Excessive punctuation or emojis
- Hashtags
"""

# Validate required keys on startup
_REQUIRED = {"LINKEDIN_ACCESS_TOKEN": LINKEDIN_ACCESS_TOKEN, "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY}
for _name, _val in _REQUIRED.items():
    if not _val:
        raise EnvironmentError(f"Missing required environment variable: {_name}. Check your .env file.")
