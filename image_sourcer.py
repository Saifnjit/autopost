import requests
from config import UNSPLASH_ACCESS_KEY


TOPIC_KEYWORDS = {
    "artificial intelligence": "technology AI future",
    "business strategy": "business strategy meeting",
    "startups funding": "startup entrepreneurship",
    "marketing growth": "marketing growth digital",
}


def fetch_image(topic: str) -> dict | None:
    """Fetch a relevant image URL from Unsplash for the given topic."""
    query = TOPIC_KEYWORDS.get(topic, topic)
    url = "https://api.unsplash.com/photos/random"
    params = {
        "query": query,
        "orientation": "landscape",
        "content_filter": "high",
    }
    headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}

    response = requests.get(url, params=params, headers=headers)

    if response.status_code != 200:
        return None

    data = response.json()
    return {
        "url": data["urls"]["regular"],
        "download_url": data["links"]["download"],
        "photographer": data["user"]["name"],
        "alt": data.get("alt_description", ""),
    }


def download_image(image_info: dict, save_path: str = "post_image.jpg") -> str | None:
    """Download image to disk and return the file path."""
    if not image_info:
        return None

    response = requests.get(image_info["download_url"], stream=True)
    if response.status_code != 200:
        return None

    with open(save_path, "wb") as f:
        for chunk in response.iter_content(1024):
            f.write(chunk)

    return save_path
