# Spotify Integration — DesktopFlow

## Setup (2 minutes, one time only)

### Step 1 — Create a free Spotify Developer App

1. Go to https://developer.spotify.com/dashboard
2. Log in with your Spotify account
3. Click **Create App**
4. Fill in:
   - App name: `DesktopFlow` (or anything)
   - Redirect URI: `http://localhost:8765/callback`  ← **this must be exact**
   - Check **Web API**
5. Click **Save**
6. On the app page, copy your **Client ID**

### Step 2 — Authorize in DesktopFlow

**Option A — Tray icon:**
Right-click tray icon → Spotify → Setup / Re-authorize…

**Option B — Editor:**
Click the **♫ Spotify** button in the toolbar

**Option C — Templates tab:**
Click the **♫ Spotify** template card

A dialog will appear. Paste your Client ID and click **Authorize with Spotify**.
Your browser opens Spotify's login page. Approve it. Done.

---

## What the widget shows

- Album art (rounded, cached)
- Track name, artist, album
- Progress bar with elapsed / total time
- ▶/⏸ Play/Pause button
- ⏮ Previous track
- ⏭ Next track
- 🔀 Shuffle state indicator
- 🔁 Repeat state indicator
- Volume icon
- Active device name

## Controls

Click directly on the control buttons on the widget.
The widget must NOT be locked (right-click tray → uncheck "Widgets Locked") — 
or set to desktop layer which is always interactive on click.

Actually: control clicks work even in locked mode because the Spotify widget
handles its own mouse events separately from the lock system.

## Token storage

Your access token is stored at:
`%APPDATA%\DesktopFlow\spotify_token.json`

It is refreshed automatically. You never need to re-authorize unless you
revoke access in Spotify's account settings.

## Disconnect

Tray → Spotify → Disconnect
This deletes the saved token. You can re-authorize at any time.

## No extra pip packages

The Spotify integration uses only Python stdlib:
`urllib`, `http.server`, `webbrowser`, `hashlib`, `base64`, `secrets`

No `spotipy`, no `requests` needed for Spotify specifically.
