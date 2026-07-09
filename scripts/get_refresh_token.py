"""
One-time helper: exchange the Spotify Authorization Code flow for a refresh
token you can paste into GitHub Actions secrets as SPOTIFY_REFRESH_TOKEN.

Run locally only. Never invoke this in CI.

Usage:
    export SPOTIFY_CLIENT_ID=...
    export SPOTIFY_CLIENT_SECRET=...
    python3 scripts/get_refresh_token.py

The script will:
  1. Open your browser to Spotify's auth page.
  2. Spin up a one-shot local server on http://127.0.0.1:3000 to catch the
     redirect and capture the auth code.
  3. Exchange the code for tokens and print the refresh token.

Spotify dashboard prerequisites:
  * Redirect URI includes exactly: http://127.0.0.1:3000
  * "Web API" is checked in APIs used.
"""

import base64
import getpass
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

REDIRECT_URI = "http://127.0.0.1:3000"
SCOPE = "user-read-recently-played"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"


def prompt_if_missing(name, is_secret=False):
    value = os.environ.get(name)
    if value:
        return value
    prompt = f"{name}: "
    return getpass.getpass(prompt) if is_secret else input(prompt).strip()


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    result = {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        CallbackHandler.result["code"] = params.get("code", [None])[0]
        CallbackHandler.result["state"] = params.get("state", [None])[0]
        CallbackHandler.result["error"] = params.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        body = (
            "<h2>Got it.</h2><p>You can close this tab and go back to your "
            "terminal.</p>"
        )
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args, **kwargs):
        return


def capture_code(expected_state):
    server = http.server.HTTPServer(("127.0.0.1", 3000), CallbackHandler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout=180)
    server.server_close()

    result = CallbackHandler.result
    if result.get("error"):
        sys.exit(f"Spotify returned an error: {result['error']}")
    if not result.get("code"):
        sys.exit("Timed out waiting for the redirect. Rerun the script.")
    if result.get("state") != expected_state:
        sys.exit("State mismatch; possible CSRF. Rerun the script.")
    return result["code"]


def exchange_code(code, client_id, client_secret):
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }
    ).encode("utf-8")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        sys.exit(f"Token exchange failed ({e.code}): {detail}")


def main():
    client_id = prompt_if_missing("SPOTIFY_CLIENT_ID")
    client_secret = prompt_if_missing("SPOTIFY_CLIENT_SECRET", is_secret=True)

    state = secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\nOpening Spotify authorization in your browser...")
    print(f"If it doesn't open, paste this URL:\n{auth_url}\n")
    webbrowser.open(auth_url)

    code = capture_code(state)
    tokens = exchange_code(code, client_id, client_secret)

    refresh = tokens.get("refresh_token")
    if not refresh:
        sys.exit(f"No refresh_token in response: {tokens}")

    print("\n" + "=" * 60)
    print("SPOTIFY_REFRESH_TOKEN:")
    print(refresh)
    print("=" * 60)
    print(
        "\nCopy the token above (the single line between the ===) and paste "
        "it into GitHub Actions secrets as SPOTIFY_REFRESH_TOKEN."
    )


if __name__ == "__main__":
    main()
