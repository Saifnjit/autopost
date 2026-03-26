"""
Run this script once to get your LinkedIn access token.
It starts a local server to handle the OAuth callback.

Usage:
    python setup_auth.py

Then visit the URL it prints, authorize the app, and your
access token will be saved automatically to .env
"""

import os
import requests
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv, set_key

load_dotenv()

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "openid profile w_member_social"

auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Authorization successful! You can close this tab.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>Authorization failed. Check your app settings.</h2>")

    def log_message(self, format, *args):
        pass  # Suppress server logs


def get_access_token(code: str) -> str:
    response = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def main():
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPES.replace(' ', '%20')}"
    )

    print("\n=== LinkedIn OAuth Setup ===")
    print("Opening your browser to authorize the app...")
    print(f"\nIf it doesn't open automatically, visit:\n{auth_url}\n")

    server = HTTPServer(("localhost", 8000), CallbackHandler)
    threading.Timer(1, lambda: webbrowser.open(auth_url)).start()
    server.handle_request()  # Handle one request then stop

    if auth_code:
        print("Authorization code received. Fetching access token...")
        token = get_access_token(auth_code)
        set_key(".env", "LINKEDIN_ACCESS_TOKEN", token)
        print("Access token saved to .env successfully!")
        print("\nYou're all set. Run `python main.py` to start the bot.")
    else:
        print("Failed to get authorization code. Check your Client ID and redirect URI settings.")


if __name__ == "__main__":
    main()
