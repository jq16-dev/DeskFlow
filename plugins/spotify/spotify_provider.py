"""
spotify_provider.py — Full Spotify Web API integration.

Flow:
  1. User runs setup_spotify() → opens browser for OAuth
  2. Local HTTP server on :8888 catches the callback code
  3. Tokens saved to %APPDATA_DeskFlow/spotify_tokens.json
  4. Auto-refresh via refresh_token before expiry
  5. DataProvider key "spotify" returns full now-playing dict

Register with DeskFlow:
    from plugins.spotify.spotify_provider import register
    register(api)  # or auto-loaded via plugin_manager
"""

import os
import json
import time
import base64
import logging
import threading
import webbrowser
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import requests

logger = logging.getLogger("DeskFlow.Spotify")

# ─── Spotify App credentials ──────────────────────────────────────────────────
# Create a free app at https://developer.spotify.com/dashboard
# Set Redirect URI to: http://localhost:8888/callback
# Then paste your Client ID and Secret below (or set as env vars).

CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID",     "YOUR_CLIENT_ID_HERE")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "YOUR_CLIENT_SECRET_HERE")
REDIRECT_URI  = "http://localhost:8888/callback"
SCOPES        = "user-read-playback-state user-read-currently-playing user-modify-playback-state"

TOKEN_FILE    = Path.home() / ".config" / "DeskFlow" / "spotify_tokens.json"
TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)

# ─── Token store ─────────────────────────────────────────────────────────────

_tokens: dict = {}
_lock   = threading.Lock()


def _load_tokens():
    global _tokens
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE) as f:
            _tokens = json.load(f)


def _save_tokens(data: dict):
    global _tokens
    _tokens = data
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _token_valid() -> bool:
    return bool(_tokens.get("access_token")) and time.time() < _tokens.get("expires_at", 0) - 30


def _refresh() -> bool:
    rt = _tokens.get("refresh_token")
    if not rt:
        logger.warning("No refresh token — please re-authenticate")
        return False
    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp  = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": rt},
        timeout=10,
    )
    if resp.status_code == 200:
        d = resp.json()
        _tokens["access_token"] = d["access_token"]
        _tokens["expires_at"]   = time.time() + d["expires_in"]
        if "refresh_token" in d:
            _tokens["refresh_token"] = d["refresh_token"]
        _save_tokens(_tokens)
        logger.info("Spotify token refreshed")
        return True
    logger.error(f"Token refresh failed: {resp.status_code} {resp.text}")
    return False


def _get_access_token() -> Optional[str]:
    with _lock:
        if _token_valid():
            return _tokens["access_token"]
        if _refresh():
            return _tokens["access_token"]
    return None


# ─── OAuth callback server ────────────────────────────────────────────────────

_auth_code: Optional[str] = None
_auth_event = threading.Event()


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _auth_code = params["code"][0]
            body = b"<html><body style='font-family:Segoe UI;background:#1a1a2e;color:#e0e0e0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;'><h2>&#10003; Spotify connected! You can close this tab.</h2></body></html>"
        else:
            body = b"<html><body>Authorization failed.</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)
        _auth_event.set()

    def log_message(self, *args): pass  # suppress server logs


def _exchange_code(code: str) -> bool:
    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    resp  = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=10,
    )
    if resp.status_code == 200:
        d = resp.json()
        _save_tokens({
            "access_token":  d["access_token"],
            "refresh_token": d.get("refresh_token",""),
            "expires_at":    time.time() + d["expires_in"],
        })
        return True
    logger.error(f"Code exchange failed: {resp.status_code} {resp.text}")
    return False


def setup_spotify() -> bool:
    """
    Open browser for Spotify OAuth. Blocks until auth completes (max 120s).
    Returns True on success.
    """
    global _auth_code
    _auth_code = None
    _auth_event.clear()

    if CLIENT_ID == "YOUR_CLIENT_ID_HERE":
        logger.error("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in spotify_provider.py or as env vars")
        return False

    # Start callback server
    server = HTTPServer(("localhost", 8888), _CallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    # Build auth URL
    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id":     CLIENT_ID,
        "scope":         SCOPES,
        "redirect_uri":  REDIRECT_URI,
    })
    url = f"https://accounts.spotify.com/authorize?{params}"
    webbrowser.open(url)
    logger.info("Spotify auth URL opened in browser")

    # Wait for callback
    got_it = _auth_event.wait(timeout=120)
    server.shutdown()

    if got_it and _auth_code:
        success = _exchange_code(_auth_code)
        if success:
            logger.info("Spotify auth complete")
        return success
    logger.warning("Spotify auth timed out or cancelled")
    return False


# ─── Spotify API helpers ──────────────────────────────────────────────────────

def _api_get(endpoint: str) -> Optional[dict]:
    token = _get_access_token()
    if not token:
        return None
    resp = requests.get(
        f"https://api.spotify.com/v1/{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=6,
    )
    if resp.status_code == 204:   # no content (nothing playing)
        return {}
    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 401:
        logger.debug("Spotify 401 — token expired, will refresh next call")
        with _lock:
            _tokens["expires_at"] = 0  # force refresh
    return None


def _api_post(endpoint: str, data: dict = None) -> bool:
    token = _get_access_token()
    if not token:
        return False
    resp = requests.post(
        f"https://api.spotify.com/v1/{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        json=data or {},
        timeout=6,
    )
    return resp.status_code in (200, 204)


def _api_put(endpoint: str, data: dict = None) -> bool:
    token = _get_access_token()
    if not token:
        return False
    resp = requests.put(
        f"https://api.spotify.com/v1/{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        json=data or {},
        timeout=6,
    )
    return resp.status_code in (200, 204)


# ─── Playback controls (callable from widget buttons / keybinds) ──────────────

def spotify_play_pause():
    d = _api_get("me/player")
    if d and d.get("is_playing"):
        requests.put("https://api.spotify.com/v1/me/player/pause",
                     headers={"Authorization": f"Bearer {_get_access_token()}"}, timeout=5)
    else:
        _api_put("me/player/play")


def spotify_next():
    token = _get_access_token()
    if token:
        requests.post("https://api.spotify.com/v1/me/player/next",
                      headers={"Authorization": f"Bearer {token}"}, timeout=5)


def spotify_prev():
    token = _get_access_token()
    if token:
        requests.post("https://api.spotify.com/v1/me/player/previous",
                      headers={"Authorization": f"Bearer {token}"}, timeout=5)


def spotify_set_volume(pct: int):
    _api_put(f"me/player/volume?volume_percent={max(0,min(100,pct))}")


# ─── Main data provider ───────────────────────────────────────────────────────

def _fetch_spotify(args: dict) -> dict:
    """
    Returns a dict with full now-playing data.
    Keys: track, artist, album, progress_ms, duration_ms, progress,
          is_playing, shuffle, repeat, volume, cover_url, track_url
    Returns {"is_playing": False} if nothing is playing.
    """
    data = _api_get("me/player/currently-playing?additional_types=track")
    if data is None:
        return {"is_playing": False, "track": "Not connected", "artist": "", "progress": 0}
    if data == {}:
        return {"is_playing": False, "track": "Nothing playing", "artist": "", "progress": 0}

    item = data.get("item", {})
    if not item:
        return {"is_playing": False, "track": "Nothing playing", "artist": "", "progress": 0}

    progress_ms  = data.get("progress_ms", 0)
    duration_ms  = item.get("duration_ms", 1)
    artists      = ", ".join(a["name"] for a in item.get("artists", []))
    album        = item.get("album", {})
    images       = album.get("images", [])
    cover_url    = images[0]["url"] if images else ""
    ext_urls     = item.get("external_urls", {})

    # Get device info
    device = data.get("device", {})

    return {
        "is_playing":   data.get("is_playing", False),
        "track":        item.get("name", ""),
        "artist":       artists,
        "album":        album.get("name", ""),
        "progress_ms":  progress_ms,
        "duration_ms":  duration_ms,
        "progress":     progress_ms / duration_ms if duration_ms else 0,
        "progress_str": _ms_to_str(progress_ms),
        "duration_str": _ms_to_str(duration_ms),
        "shuffle":      data.get("shuffle_state", False),
        "repeat":       data.get("repeat_state", "off"),
        "volume":       device.get("volume_percent", 100),
        "device":       device.get("name", ""),
        "cover_url":    cover_url,
        "track_url":    ext_urls.get("spotify", ""),
        "context_type": data.get("context", {}).get("type", ""),
    }


def _ms_to_str(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


# ─── Plugin registration ──────────────────────────────────────────────────────

def register(api):
    _load_tokens()
    api.register_data_provider("spotify", _fetch_spotify, ttl=2.0)
    logger.info("Spotify provider registered (TTL=2s)")
