"""
Scores a LinkedIn post for viral potential using Claude.
Only posts that score 7/10 or above get published.
"""

import anthropic
import json
from config import ANTHROPIC_API_KEY
from settings import MIN_VIRAL_SCORE


def check_viral_potential(post_text: str) -> dict:
    """
    Ask Claude to score the post for viral potential.
    Returns: { "score": int, "reason": str, "passes": bool }
    """
    if not post_text or not post_text.strip():
        return {"score": 0, "reason": "Empty post", "passes": False, "weakness": "No content"}

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""
You are a LinkedIn content strategist who knows exactly what goes viral.

Score this LinkedIn post for viral potential on a scale of 1-10 based on:
- Hook strength (does the first line stop the scroll?)
- Emotional trigger (fear, curiosity, awe, controversy?)
- Relatability (do professionals instantly connect with this?)
- Comment potential (does it make people WANT to respond?)
- Shareability (would someone send this to a colleague?)
- Timeliness (is it about something people care about RIGHT NOW?)
- Specificity (does it reference a real company, person, number, or event? Abstract observations with no concrete facts score max 4)
- Topic relevance (is it about AI, tech, business, startups or strategy? If not, score max 3)

POST TO SCORE:
---
{post_text}
---

Return ONLY valid JSON, nothing else:
{{
  "score": <number 1-10>,
  "hook_score": <number 1-10>,
  "emotion_score": <number 1-10>,
  "comment_potential": <number 1-10>,
  "reason": "<one sentence explaining the score>",
  "weakness": "<the single biggest thing holding it back>",
  "passes": <true if score >= {MIN_VIRAL_SCORE}, false otherwise>
}}
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            timeout=30,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        result["passes"] = result.get("score", 0) >= MIN_VIRAL_SCORE
        return result

    except json.JSONDecodeError as e:
        print(f"  Viral check JSON error: {e}")
        return {"score": 0, "reason": "Parse error", "passes": False, "weakness": "Unknown"}
    except Exception as e:
        print(f"  Viral check API error: {e}")
        return {"score": 0, "reason": "API error", "passes": False, "weakness": "Unknown"}
