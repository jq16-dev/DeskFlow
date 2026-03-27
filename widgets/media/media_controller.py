"""
media_controller.py — DeskFlow 2026 Media Detection Engine
============================================================
Uses pycaw (Windows Core Audio) + ctypes window-title scraping.
NO winsdk. NO asyncio. Fully synchronous.

Detection chain:
  1. pycaw AudioSessionManager -> enumerate active audio sessions
     -> identify process by PID -> map to known app
  2. Window-title scraping     -> parse artist/title from window captions
  3. iTunes Search API         -> album art (no auth needed)
"""

import ctypes
import ctypes.wintypes
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("DeskFlow.Media")

# ── Global shared state ───────────────────────────────────────────────────────

_state: Dict[str, Any] = {
    "title": "", "artist": "", "album": "", "app_name": "",
    "playing": False, "progress": 0.0,
    "duration_s": 0, "position_s": 0,
    "source": "", "art_data": None, "art_url": "", "pid": 0,
}
_lock    = threading.Lock()
_running = False
_thread: Optional[threading.Thread] = None


def get_state() -> dict:
    with _lock:
        return dict(_state)


def _set_state(**kw):
    with _lock:
        _state.update(kw)


def _clear_state():
    with _lock:
        _state.update({
            "title": "", "artist": "", "album": "", "app_name": "",
            "playing": False, "progress": 0.0,
            "duration_s": 0, "position_s": 0,
            "source": "", "art_data": None, "art_url": "", "pid": 0,
        })


# ── Process helpers ───────────────────────────────────────────────────────────

def _pid_to_exe(pid: int) -> str:
    """Return lowercase .exe name for a PID. Pure ctypes."""
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        hnd = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not hnd:
            return ""
        buf = ctypes.create_unicode_buffer(512)
        sz  = ctypes.c_ulong(512)
        ctypes.windll.kernel32.QueryFullProcessImageNameW(hnd, 0, buf, ctypes.byref(sz))
        ctypes.windll.kernel32.CloseHandle(hnd)
        return os.path.basename(buf.value).lower()
    except Exception:
        return ""


def _classify_exe(exe: str) -> str:
    exe = exe.lower()
    if "spotify"  in exe: return "spotify"
    if "vlc"      in exe: return "vlc"
    if "chrome"   in exe: return "chrome"
    if "msedge"   in exe: return "edge"
    if "firefox"  in exe: return "firefox"
    if "wmplayer" in exe: return "wmp"
    if "video.ui" in exe: return "movies"
    if "groove"   in exe: return "groove"
    if "foobar"   in exe: return "foobar"
    if "musicbee" in exe: return "musicbee"
    if "aimp"     in exe: return "aimp"
    if "winamp"   in exe: return "winamp"
    return "system"


_SOURCE_NAMES = {
    "spotify":  "Spotify",
    "vlc":      "VLC",
    "chrome":   "Chrome",
    "edge":     "Edge",
    "firefox":  "Firefox",
    "wmp":      "Windows Media Player",
    "movies":   "Movies & TV",
    "groove":   "Groove Music",
    "foobar":   "foobar2000",
    "musicbee": "MusicBee",
    "aimp":     "AIMP",
    "winamp":   "Winamp",
    "system":   "Media",
}


# ── pycaw session enumeration ─────────────────────────────────────────────────

def _get_audio_sessions() -> List[Tuple[int, str, bool]]:
    """
    Return list of (pid, source_key, is_active) using pycaw.
    Active sessions (currently producing audio) are first.
    """
    try:
        from pycaw.pycaw import AudioUtilities, AudioSessionState
    except ImportError:
        return []

    results = []
    try:
        sessions = AudioUtilities.GetAllSessions()
        for s in sessions:
            try:
                pid = getattr(s, "ProcessId", 0)
                if not pid:
                    continue
                state = getattr(s, "State", None)
                active = (state == AudioSessionState.AudioSessionStateActive
                          if state is not None else True)
                exe    = _pid_to_exe(pid)
                source = _classify_exe(exe)
                results.append((pid, source, active))
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"pycaw enum error: {e}")
        return []

    PRIORITY = ["spotify", "vlc", "chrome", "edge", "firefox",
                "wmp", "movies", "groove", "foobar", "musicbee",
                "aimp", "winamp", "system"]

    def _sort_key(item):
        _, src, active = item
        p = PRIORITY.index(src) if src in PRIORITY else 98
        return (0 if active else 1, p)

    results.sort(key=_sort_key)
    return results


# ── Window title helpers ──────────────────────────────────────────────────────

def _titles_for_pid(pid: int) -> List[str]:
    """All visible window titles belonging to a PID."""
    out = []
    IsVisible    = ctypes.windll.user32.IsWindowVisible
    GetLen       = ctypes.windll.user32.GetWindowTextLengthW
    GetText      = ctypes.windll.user32.GetWindowTextW
    GetPidForHwnd = ctypes.windll.user32.GetWindowThreadProcessId

    def _cb(hwnd, _):
        if not IsVisible(hwnd): return True
        proc = ctypes.c_ulong(0)
        GetPidForHwnd(hwnd, ctypes.byref(proc))
        if proc.value != pid: return True
        ln = GetLen(hwnd)
        if ln <= 0: return True
        buf = ctypes.create_unicode_buffer(ln + 1)
        GetText(hwnd, buf, ln + 1)
        t = buf.value.strip()
        if t: out.append(t)
        return True

    try:
        F = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL,
                                ctypes.wintypes.HWND,
                                ctypes.wintypes.LPARAM)
        ctypes.windll.user32.EnumWindows(F(_cb), 0)
    except Exception:
        pass
    return out


def _all_titles() -> List[Tuple[str, int]]:
    """(title, pid) for every visible window."""
    out = []
    IsVisible    = ctypes.windll.user32.IsWindowVisible
    GetLen       = ctypes.windll.user32.GetWindowTextLengthW
    GetText      = ctypes.windll.user32.GetWindowTextW
    GetPidForHwnd = ctypes.windll.user32.GetWindowThreadProcessId

    def _cb(hwnd, _):
        if not IsVisible(hwnd): return True
        ln = GetLen(hwnd)
        if ln <= 0: return True
        buf = ctypes.create_unicode_buffer(ln + 1)
        GetText(hwnd, buf, ln + 1)
        t = buf.value.strip()
        if t:
            p = ctypes.c_ulong(0)
            GetPidForHwnd(hwnd, ctypes.byref(p))
            out.append((t, p.value))
        return True

    try:
        F = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL,
                                ctypes.wintypes.HWND,
                                ctypes.wintypes.LPARAM)
        ctypes.windll.user32.EnumWindows(F(_cb), 0)
    except Exception:
        pass
    return out


# ── Per-app parsers ───────────────────────────────────────────────────────────

def _parse_spotify(titles):
    for t in titles:
        tl = t.lower()
        if tl in ("spotify", "spotify free", "spotify premium"):
            return {"title": "Spotify", "artist": "", "album": "", "playing": False}
        if " - " in t and "download" not in tl and "update" not in tl:
            p = t.split(" - ", 1)
            if p[0].strip() and p[1].strip():
                return {"title": p[1].strip(), "artist": p[0].strip(),
                        "album": "", "playing": True}
    return None


def _parse_vlc(titles):
    for t in titles:
        if "vlc media player" not in t.lower():
            continue
        clean = t
        for s in (" - VLC media player", " — VLC media player", "VLC media player"):
            clean = clean.replace(s, "").strip()
        if not clean:
            continue
        if " - " in clean:
            p = clean.split(" - ", 1)
            return {"title": p[1].strip(), "artist": p[0].strip(),
                    "album": "", "playing": True}
        return {"title": clean, "artist": "", "album": "", "playing": True}
    return None


def _parse_browser(titles):
    for t in titles:
        tl = t.lower()
        # Strip browser chrome suffix
        for s in (" - Google Chrome", " - Microsoft Edge", " - Firefox",
                  " - Chromium", "- Google Chrome", "- Microsoft Edge"):
            t = t.replace(s, "").strip()
        tl = t.lower()

        if "youtube" in tl:
            track = t.replace("▶ ", "").strip()
            return {"title": track, "artist": "YouTube", "album": "", "playing": True}
        if "soundcloud" in tl and " - " in t:
            p = t.split("|")[0].strip()
            if " - " in p:
                b = p.split(" - ", 1)
                return {"title": b[1].strip(), "artist": b[0].strip(),
                        "album": "", "playing": True}
        if "spotify" in tl and " - " in t:
            p = t.split(" - ")
            if len(p) >= 2:
                return {"title": p[0].strip(), "artist": p[1].strip(),
                        "album": "", "playing": True}
        if " - " in t:
            p = t.split(" - ", 1)
            return {"title": p[0].strip(), "artist": p[1].strip(),
                    "album": "", "playing": True}
    return None


def _parse_wmp(titles):
    for t in titles:
        if "windows media player" in t.lower():
            clean = t.lower().replace("windows media player", "").strip(" -–")
            if clean:
                return {"title": clean.title(), "artist": "", "album": "", "playing": True}
    return None


def _parse_generic(titles):
    for t in titles:
        if t and " - " in t:
            p = t.split(" - ", 1)
            return {"title": p[0].strip(), "artist": p[1].strip(),
                    "album": "", "playing": True}
    return None


_PARSERS = {
    "spotify": _parse_spotify,
    "vlc":     _parse_vlc,
    "chrome":  _parse_browser,
    "edge":    _parse_browser,
    "firefox": _parse_browser,
    "wmp":     _parse_wmp,
}


# ── Album art (iTunes Search API, no auth) ────────────────────────────────────

_art_cache: Dict[str, Optional[bytes]] = {}


def _fetch_art(artist: str, title: str) -> Optional[bytes]:
    key = f"{artist}|{title}"
    if key in _art_cache:
        return _art_cache[key]
    try:
        import requests
        q   = f"{artist} {title}".strip()
        url = (f"https://itunes.apple.com/search"
               f"?term={requests.utils.quote(q)}&limit=1&entity=song")
        r = requests.get(url, timeout=4)
        if r.ok:
            results = r.json().get("results", [])
            if results:
                art_url = results[0].get("artworkUrl100", "").replace(
                    "100x100bb", "300x300bb")
                if art_url:
                    ar = requests.get(art_url, timeout=4)
                    if ar.ok:
                        data = ar.content
                        if len(_art_cache) > 30:
                            _art_cache.pop(next(iter(_art_cache)))
                        _art_cache[key] = data
                        return data
    except Exception as e:
        logger.debug(f"Art fetch: {e}")
    _art_cache[key] = None
    return None


# ── Main detection ────────────────────────────────────────────────────────────

def _detect() -> Optional[dict]:
    # 1. pycaw sessions
    sessions = _get_audio_sessions()
    for pid, source, active in sessions:
        titles = _titles_for_pid(pid)
        if not titles:
            continue
        parser = _PARSERS.get(source, _parse_generic)
        parsed = parser(titles)
        if parsed and parsed.get("title"):
            app_name = _SOURCE_NAMES.get(source, source.title())
            result = {
                "title":      parsed["title"],
                "artist":     parsed.get("artist", ""),
                "album":      parsed.get("album", ""),
                "app_name":   app_name,
                "playing":    parsed.get("playing", True),
                "progress":   parsed.get("progress", 0.0),
                "duration_s": parsed.get("duration_s", 0),
                "position_s": parsed.get("position_s", 0),
                "source":     source,
                "art_data":   None,
                "art_url":    "",
                "pid":        pid,
            }
            # Album art
            if result["title"] and result["artist"]:
                art = _fetch_art(result["artist"], result["title"])
                if art:
                    result["art_data"] = art
                    result["art_url"]  = f"{result['artist']}|{result['title']}"
            return result

    # 2. Fallback: scan all window titles
    MARKERS = {
        "spotify":       ("spotify",       _parse_spotify),
        "vlc media":     ("vlc",           _parse_vlc),
        "- youtube":     ("chrome",        _parse_browser),
        "soundcloud":    ("chrome",        _parse_browser),
        "windows media": ("wmp",           _parse_wmp),
        "foobar2000":    ("foobar",        _parse_generic),
        "musicbee":      ("musicbee",      _parse_generic),
        "aimp":          ("aimp",          _parse_generic),
        "winamp":        ("winamp",        _parse_generic),
    }
    for title_str, pid in _all_titles():
        tl = title_str.lower()
        for marker, (src, parser_fn) in MARKERS.items():
            if marker in tl:
                parsed = parser_fn([title_str])
                if parsed and parsed.get("title"):
                    app_name = _SOURCE_NAMES.get(src, src.title())
                    return {
                        "title":      parsed["title"],
                        "artist":     parsed.get("artist", ""),
                        "album":      parsed.get("album", ""),
                        "app_name":   app_name,
                        "playing":    parsed.get("playing", True),
                        "progress":   0.0,
                        "duration_s": 0,
                        "position_s": 0,
                        "source":     src,
                        "art_data":   None,
                        "art_url":    "",
                        "pid":        pid,
                    }
    return None


# ── Media controls ────────────────────────────────────────────────────────────

_WM_APPCOMMAND   = 0x0319
_CMD_PLAY_PAUSE  = 46
_CMD_NEXT        = 11
_CMD_PREV        = 12
_VK_PLAY_PAUSE   = 0xB3
_VK_NEXT         = 0xB0
_VK_PREV         = 0xB1


def _media_key(vk: int):
    EXT = 0x0001
    UP  = 0x0002
    ctypes.windll.user32.keybd_event(vk, 0, EXT, 0)
    ctypes.windll.user32.keybd_event(vk, 0, EXT | UP, 0)


def _appcommand(pid: int, cmd: int):
    """Send WM_APPCOMMAND to window belonging to pid."""
    try:
        IsVisible    = ctypes.windll.user32.IsWindowVisible
        GetPid       = ctypes.windll.user32.GetWindowThreadProcessId
        found        = [None]

        def _cb(hwnd, _):
            if not IsVisible(hwnd): return True
            p = ctypes.c_ulong(0)
            GetPid(hwnd, ctypes.byref(p))
            if p.value == pid:
                found[0] = hwnd
                return False
            return True

        F = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL,
                                ctypes.wintypes.HWND,
                                ctypes.wintypes.LPARAM)
        ctypes.windll.user32.EnumWindows(F(_cb), 0)
        if found[0]:
            LPARAM = (cmd << 4) | 0x000F0000
            ctypes.windll.user32.SendMessageW(found[0], _WM_APPCOMMAND,
                                              found[0], LPARAM)
    except Exception as e:
        logger.debug(f"AppCommand error: {e}")


def play_pause():
    pid = _state.get("pid", 0)
    if pid:
        _appcommand(pid, _CMD_PLAY_PAUSE)
    else:
        _media_key(_VK_PLAY_PAUSE)


def next_track():
    pid = _state.get("pid", 0)
    if pid:
        _appcommand(pid, _CMD_NEXT)
    else:
        _media_key(_VK_NEXT)


def prev_track():
    pid = _state.get("pid", 0)
    if pid:
        _appcommand(pid, _CMD_PREV)
    else:
        _media_key(_VK_PREV)


# ── Volume control via pycaw ─────────────────────────────────────────────────

def get_volume() -> float:
    """Return master volume 0.0–1.0. Returns -1 on error (non-Windows)."""
    if sys.platform != "win32":
        return -1.0
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        iface   = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol     = iface.QueryInterface(IAudioEndpointVolume)
        return round(float(vol.GetMasterVolumeLevelScalar()), 3)
    except Exception as e:
        logger.debug(f"get_volume error: {e}")
        return -1.0


def set_volume(level: float):
    """Set master volume. level: 0.0 (mute) – 1.0 (max)."""
    if sys.platform != "win32":
        return
    level = max(0.0, min(1.0, float(level)))
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        iface   = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol     = iface.QueryInterface(IAudioEndpointVolume)
        vol.SetMasterVolumeLevelScalar(level, None)
    except Exception as e:
        logger.debug(f"set_volume error: {e}")


def volume_up(step: float = 0.05):
    """Increase master volume by step."""
    cur = get_volume()
    if cur >= 0:
        set_volume(cur + step)


def volume_down(step: float = 0.05):
    """Decrease master volume by step."""
    cur = get_volume()
    if cur >= 0:
        set_volume(cur - step)


def mute_toggle():
    """Toggle system mute on/off."""
    if sys.platform != "win32":
        return
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        iface   = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol     = iface.QueryInterface(IAudioEndpointVolume)
        vol.SetMute(not vol.GetMute(), None)
    except Exception as e:
        logger.debug(f"mute_toggle error: {e}")


# ── Background polling ────────────────────────────────────────────────────────

def _poll_loop(interval: float):
    global _running
    while _running:
        try:
            result = _detect()
            if result:
                _set_state(**result)
            else:
                _clear_state()
        except Exception as e:
            logger.debug(f"Poll error: {e}")
        time.sleep(max(0.5, interval))


def start(interval: float = 2.0):
    global _running, _thread
    if _running:
        return
    if sys.platform != "win32":
        logger.debug("Media controller: non-Windows — skipping")
        return
    _running = True
    _thread = threading.Thread(target=_poll_loop, args=(interval,), daemon=True)
    _thread.start()
    logger.info(f"Media controller started (interval={interval}s)")


def stop():
    global _running
    _running = False
