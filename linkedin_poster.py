import requests
import os
import time
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import LINKEDIN_ACCESS_TOKEN

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LINKEDIN_API = "https://api.linkedin.com/v2"
TIMEOUT = 30  # seconds for all API calls


def _make_session() -> requests.Session:
    """Session with retry + SSL tolerance."""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_profile_id() -> str:
    session = _make_session()
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    response = session.get(f"{LINKEDIN_API}/userinfo", headers=headers, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["sub"]


def upload_image(image_path: str, author_urn: str) -> str | None:
    session = _make_session()
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    register_payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": f"urn:li:person:{author_urn}",
            "serviceRelationships": [
                {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
            ],
        }
    }
    try:
        reg_response = session.post(
            f"{LINKEDIN_API}/assets?action=registerUpload",
            headers=headers,
            json=register_payload,
            timeout=TIMEOUT,
        )
    except Exception as e:
        print(f"Image registration request failed: {e}")
        return None

    if reg_response.status_code != 200:
        print(f"Image registration failed: {reg_response.text}")
        return None

    try:
        reg_data = reg_response.json()
        upload_url = reg_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = reg_data["value"]["asset"]
    except (KeyError, ValueError) as e:
        print(f"Image registration response malformed: {e}")
        return None

    with open(image_path, "rb") as f:
        try:
            upload_response = session.put(
                upload_url,
                headers={"Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}"},
                data=f,
                timeout=60,
                verify=False,
            )
        except Exception as e:
            print(f"Image upload request failed: {e}")
            return None

    if upload_response.status_code not in (200, 201):
        print(f"Image upload failed: {upload_response.text}")
        return None

    return asset


def upload_video(video_path: str, author_urn: str) -> str | None:
    session = _make_session()
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    register_payload = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
            "owner": f"urn:li:person:{author_urn}",
            "serviceRelationships": [
                {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
            ],
        }
    }

    try:
        reg_response = session.post(
            f"{LINKEDIN_API}/assets?action=registerUpload",
            headers=headers,
            json=register_payload,
            timeout=TIMEOUT,
        )
    except Exception as e:
        print(f"Video registration request failed: {e}")
        return None

    if reg_response.status_code != 200:
        print(f"Video registration failed: {reg_response.text}")
        return None

    try:
        reg_data = reg_response.json()
        upload_url = reg_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = reg_data["value"]["asset"]
    except (KeyError, ValueError) as e:
        print(f"Video registration response malformed: {e}")
        return None

    file_size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        try:
            upload_response = session.put(
                upload_url,
                headers={
                    "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(file_size),
                },
                data=f,
                timeout=120,
                verify=False,
            )
        except Exception as e:
            print(f"Video upload request failed: {e}")
            return None

    if upload_response.status_code not in (200, 201):
        print(f"Video upload failed: {upload_response.text}")
        return None

    print("Waiting for LinkedIn to process video...")
    time.sleep(8)
    return asset


def post_to_linkedin(text: str, video_path: str | None = None, image_path: str | None = None) -> bool:
    """Post text with optional image or video to LinkedIn."""
    # Enforce LinkedIn character limit
    if len(text) > 3000:
        text = text[:2997] + "..."

    session = _make_session()
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    try:
        author_id = get_profile_id()
    except Exception as e:
        print(f"Failed to get profile ID: {e}")
        return False

    author_urn = f"urn:li:person:{author_id}"

    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    # Attach media if available
    asset = None
    if video_path and os.path.exists(video_path):
        asset = upload_video(video_path, author_id)
        if asset:
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "VIDEO"
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                {"status": "READY", "description": {"text": ""}, "media": asset, "title": {"text": ""}}
            ]
        else:
            print("Video upload failed — posting text only")

    elif image_path and os.path.exists(image_path):
        asset = upload_image(image_path, author_id)
        if asset:
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "IMAGE"
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                {"status": "READY", "description": {"text": ""}, "media": asset, "title": {"text": ""}}
            ]
        else:
            print("Image upload failed — posting text only")

    try:
        response = session.post(
            f"{LINKEDIN_API}/ugcPosts",
            headers=headers,
            json=payload,
            timeout=TIMEOUT,
        )
    except Exception as e:
        print(f"Post request failed: {e}")
        return False

    if response.status_code == 201:
        print(f"Posted successfully: {response.headers.get('X-RestLi-Id', '')}")
        return True
    else:
        print(f"Post failed ({response.status_code}): {response.text}")
        return False
