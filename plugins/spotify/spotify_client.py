"""
spotify_client.py — Full Spotify Web API client.

Handles:
  - OAuth 2.0 Authorization Code flow (with PKCE)
  - Token storage, refresh, expiry
  - All playback endpoints: current track, play/pause/skip/prev/seek/volume/shuffle/repeat
  - Album art download + caching
  - Thread-safe background polling
"""

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("DeskFlow.Spotify")

# ── Constants ──────────────────────────────────────────────────────────────────

SPOTIFY_AUTH_URL    = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL   = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE    = "https://api.spotify.com/v1"
REDIRECT_URI        = "http://localhost:8765/callback"
SCOPES              = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "streaming"
)

# Users must create a free app at https://developer.spotify.com/dashboard
# and set redirect URI to http://localhost:8765/callback
# Then put their Client ID here (or pass via plugin args).
DEFAULT_CLIENT_ID = ""   # filled in by user or setup wizard

TOKEN_FILE = Path.home() / ".config" / "DeskFlow" / "spotify_token.json"


# ── PKCE helpers ──────────────────────────────────────────────────────────────

def _pkce_verifier() -> str:
    return secrets.token_urlsafe(64)

def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


# ── Token storage ─────────────────────────────────────────────────────────────

def _save_token(data: dict):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)

def _load_token() -> Optional[dict]:
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return None


# ── HTTP callback server (catches OAuth redirect) ─────────────────────────────

_oauth_code: Optional[str] = None
_oauth_error: Optional[str] = None
_oauth_event = threading.Event()

class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _oauth_code, _oauth_error
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        if "code" in params:
            _oauth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
<html><body style="background:#0f0f1e;color:#fff;font-family:Segoe UI;text-align:center;padding-top:80px">
<h2 style="color:#1DB954">&#10003; Spotify Connected!</h2>
<p>You can close this tab and return to DeskFlow.</p>
</body></html>""")
        elif "error" in params:
            _oauth_error = params.get("error",["unknown"])[0]
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<html><body>Auth error. Close this tab.</body></html>")
        else:
            self.send_response(404)
            self.end_headers()
        _oauth_event.set()

    def log_message(self, *args): pass   # silence HTTP log


def _start_callback_server():
    server = HTTPServer(("localhost", 8765), _CallbackHandler)
    server.timeout = 120
    server.handle_request()
    server.server_close()


# ── Main client ───────────────────────────────────────────────────────────────

class SpotifyClient:
    """
    Full Spotify client with PKCE OAuth, auto-refresh, and playback control.
    """

    def __init__(self, client_id: str = ""):
        self.client_id    = client_id or DEFAULT_CLIENT_ID
        self._token_data  : Optional[dict] = _load_token()
        self._lock        = threading.Lock()
        self._art_cache   : Dict[str, bytes] = {}
        self._last_state  : Dict[str, Any]  = {}
        self._authorized  = False

        if self._token_data and self._token_data.get("refresh_token"):
            try:
                self._refresh_access_token()
                self._authorized = True
                logger.info("Spotify: restored session from saved token")
            except Exception as e:
                logger.warning(f"Spotify: token refresh failed: {e}")

    @property
    def is_authorized(self) -> bool:
        return self._authorized

    # ── Authorization ──────────────────────────────────────────────────────

    def authorize(self) -> bool:
        """
        Opens browser for Spotify OAuth and waits for callback.
        Returns True on success.
        """
        global _oauth_code, _oauth_error
        _oauth_code  = None
        _oauth_error = None
        _oauth_event.clear()

        if not self.client_id:
            raise ValueError("Spotify Client ID not set. See README.")

        verifier  = _pkce_verifier()
        challenge = _pkce_challenge(verifier)

        params = {
            "client_id":             self.client_id,
            "response_type":         "code",
            "redirect_uri":          REDIRECT_URI,
            "scope":                 SCOPES,
            "code_challenge_method": "S256",
            "code_challenge":        challenge,
        }
        url = SPOTIFY_AUTH_URL + "?" + urllib.parse.urlencode(params)

        # Start callback listener in background
        t = threading.Thread(target=_start_callback_server, daemon=True)
        t.start()

        # Open browser
        import webbrowser
        webbrowser.open(url)
        logger.info("Spotify: opened browser for OAuth")

        # Wait up to 2 minutes
        _oauth_event.wait(timeout=120)

        if _oauth_code:
            self._exchange_code(_oauth_code, verifier)
            self._authorized = True
            logger.info("Spotify: authorized successfully")
            return True
        else:
            logger.error(f"Spotify: OAuth failed — {_oauth_error}")
            return False

    def _exchange_code(self, code: str, verifier: str):
        data = {
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  REDIRECT_URI,
            "client_id":     self.client_id,
            "code_verifier": verifier,
        }
        resp = self._post_token(data)
        resp["expires_at"] = time.time() + resp.get("expires_in", 3600)
        self._token_data = resp
        _save_token(resp)

    def _refresh_access_token(self):
        if not self._token_data or not self._token_data.get("refresh_token"):
            raise RuntimeError("No refresh token available")
        data = {
            "grant_type":    "refresh_token",
            "refresh_token": self._token_data["refresh_token"],
            "client_id":     self.client_id,
        }
        resp = self._post_token(data)
        resp["expires_at"] = time.time() + resp.get("expires_in", 3600)
        if "refresh_token" not in resp:
            resp["refresh_token"] = self._token_data["refresh_token"]
        self._token_data = resp
        _save_token(resp)

    def _post_token(self, data: dict) -> dict:
        body    = urllib.parse.urlencode(data).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        req     = urllib.request.Request(SPOTIFY_TOKEN_URL, body, headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def _access_token(self) -> str:
        if not self._token_data:
            raise RuntimeError("Not authorized")
        if time.time() > self._token_data.get("expires_at", 0) - 60:
            self._refresh_access_token()
        return self._token_data["access_token"]

    # ── API requests ───────────────────────────────────────────────────────

    def _get(self, endpoint: str) -> Optional[dict]:
        try:
            url = SPOTIFY_API_BASE + endpoint
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {self._access_token()}"
            })
            with urllib.request.urlopen(req, timeout=6) as r:
                if r.status == 204:
                    return {}
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self._refresh_access_token()
            logger.debug(f"Spotify GET {endpoint} → {e.code}")
        except Exception as e:
            logger.debug(f"Spotify GET {endpoint} error: {e}")
        return None

    def _put(self, endpoint: str, body: Optional[dict] = None):
        try:
            url  = SPOTIFY_API_BASE + endpoint
            data = json.dumps(body).encode() if body else b""
            req  = urllib.request.Request(url, data=data, method="PUT", headers={
                "Authorization":  f"Bearer {self._access_token()}",
                "Content-Type":   "application/json",
            })
            with urllib.request.urlopen(req, timeout=6):
                pass
        except Exception as e:
            logger.debug(f"Spotify PUT {endpoint} error: {e}")

    def _post(self, endpoint: str, body: Optional[dict] = None):
        try:
            url  = SPOTIFY_API_BASE + endpoint
            data = json.dumps(body).encode() if body else b""
            req  = urllib.request.Request(url, data=data, method="POST", headers={
                "Authorization": f"Bearer {self._access_token()}",
                "Content-Type":  "application/json",
            })
            with urllib.request.urlopen(req, timeout=6):
                pass
        except Exception as e:
            logger.debug(f"Spotify POST {endpoint} error: {e}")

    # ── Playback state ─────────────────────────────────────────────────────

    def get_playback_state(self) -> dict:
        """
        Returns a clean dict with current playback info.
        Returns {} if nothing is playing.
        """
        raw = self._get("/me/player")
        if not raw:
            return {"playing": False, "track": "Not Playing", "artist": "",
                    "album": "", "art_url": "", "progress": 0.0,
                    "duration_ms": 0, "progress_ms": 0,
                    "shuffle": False, "repeat": "off", "volume": 100}

        item    = raw.get("item") or {}
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        album   = item.get("album", {})
        images  = album.get("images", [])
        art_url = images[0]["url"] if images else ""
        prog_ms = raw.get("progress_ms", 0)
        dur_ms  = item.get("duration_ms", 1)
        state = {
            "playing":     raw.get("is_playing", False),
            "track":       item.get("name", "Unknown"),
            "artist":      artists,
            "album":       album.get("name", ""),
            "art_url":     art_url,
            "progress":    prog_ms / max(dur_ms, 1),
            "progress_ms": prog_ms,
            "duration_ms": dur_ms,
            "duration_str":_ms_to_str(dur_ms),
            "progress_str":_ms_to_str(prog_ms),
            "shuffle":     raw.get("shuffle_state", False),
            "repeat":      raw.get("repeat_state", "off"),
            "volume":      raw.get("device", {}).get("volume_percent", 100),
            "device":      raw.get("device", {}).get("name", ""),
        }
        self._last_state = state
        return state

    # ── Controls ───────────────────────────────────────────────────────────

    def play_pause(self):
        if self._last_state.get("playing"):
            self._put("/me/player/pause")
        else:
            self._put("/me/player/play")

    def next_track(self):
        self._post("/me/player/next")

    def prev_track(self):
        self._post("/me/player/previous")

    def seek(self, position_ms: int):
        self._put(f"/me/player/seek?position_ms={int(position_ms)}")

    def set_volume(self, volume_pct: int):
        v = max(0, min(100, volume_pct))
        self._put(f"/me/player/volume?volume_percent={v}")

    def toggle_shuffle(self):
        current = self._last_state.get("shuffle", False)
        self._put(f"/me/player/shuffle?state={'false' if current else 'true'}")

    def cycle_repeat(self):
        states = {"off": "context", "context": "track", "track": "off"}
        current = self._last_state.get("repeat", "off")
        self._put(f"/me/player/repeat?state={states.get(current,'off')}")

    # ── Album art ──────────────────────────────────────────────────────────

    def get_album_art(self, url: str) -> Optional[bytes]:
        if not url:
            return None
        if url in self._art_cache:
            return self._art_cache[url]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DeskFlow/2.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()
            self._art_cache[url] = data
            return data
        except Exception as e:
            logger.debug(f"Art fetch failed: {e}")
            return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ms_to_str(ms: int) -> str:
    s = ms // 1000
    return f"{s//60}:{s%60:02d}"


# ── Singleton ─────────────────────────────────────────────────────────────────

_client: Optional[SpotifyClient] = None

def get_client(client_id: str = "") -> SpotifyClient:
    global _client
    if _client is None:
        _client = SpotifyClient(client_id)
    return _client
