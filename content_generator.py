import anthropic
import json
from config import ANTHROPIC_API_KEY, BRAND_VOICE


def generate_post(article: dict) -> dict:
    """Generate a LinkedIn caption for the article. Returns dict with 'caption' key."""
    title = (article.get("title") or "").strip()
    description = (article.get("description") or "").strip()
    source = (article.get("source") or "").strip()

    if not title:
        raise ValueError("Article has no title")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""
{BRAND_VOICE}

A trending news story just broke. Write a LinkedIn post caption about it.

Article title: {title}
Article summary: {description}
Source: {source}

Rules:
- Ground the post in at least one specific fact from the article — a company name, person, number, dollar amount, or concrete event. No abstract observations with nothing real behind them.
- Sound like a sharp, plugged-in professional who actually keeps up with tech — not a LinkedIn guru, not a teenager
- First line hits immediately. short. no fluff. makes you stop scrolling.
- Write how smart people text — lowercase when it feels natural, punchy sentence rhythm, nothing forced
- Reactions should feel genuine — "this is actually huge", "nobody's talking about this", "wild timing on this one" — only when it fits naturally, never crammed in
- No "bro", no "no cap", no "slay" — that's the old man trying to sound young version. avoid it.
- Dry wit is welcome. understatement works. confidence without trying too hard.
- Under 150 words. every line break earns its place.
- End with a question or take that makes someone in tech or business actually want to respond
- No hashtags. no emojis unless one at the very end if it fits. no corporate speak.

Return ONLY valid JSON:
{{"caption": "the full linkedin caption here"}}
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        timeout=30,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    try:
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        if "caption" not in result or not result["caption"]:
            raise ValueError("Missing caption in response")
        return result
    except Exception as e:
        print(f"  Caption parse error: {e}")
        # Use raw text as fallback if it looks like actual content
        if len(raw) > 20:
            return {"caption": raw}
        raise
