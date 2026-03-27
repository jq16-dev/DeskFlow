# DeskFlow 2026

A modern Windows desktop widget engine. Clean, fast, iOS-inspired.

---

## Quick Start

```
pip install -r requirements.txt
python main.py
```

---

## Installation

### 1. Requirements
- **Python 3.10+** (3.11 recommended)
- **Windows 10 / 11** (primary platform)

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

Required packages:
| Package | Purpose |
|---------|---------|
| PySide6 | UI framework |
| psutil | System metrics (CPU, RAM, disk, network) |
| requests | Weather, news, stocks, crypto |
| pycaw | Windows audio session detection (media widget) |

### 3. Add custom fonts (optional)
1. Download font files (`.ttf` or `.otf`) from [Google Fonts](https://fonts.google.com)
2. Copy them to: `assets/fonts/`
3. Restart DeskFlow — fonts load automatically
4. Select them in Widget Editor → element → Font Family

**Built-in safe fonts** (no extra files needed):
`Segoe UI`, `Arial`, `Calibri`, `Consolas`, `Courier New`, `Georgia`, `Tahoma`, `Verdana`

### 4. Run
```bash
python main.py
```
DeskFlow runs as a system tray app. Double-click the tray icon to open Widget Studio.

---

## Building a Windows .exe

```bash
pip install pyinstaller
pyinstaller DeskFlow.spec
```
Output: `dist/DeskFlow.exe`

---

## Weather Widget

- Uses **Open-Meteo** API — free, no API key required
- Default location: **Islamabad, Pakistan** (lat 33.7167, lon 72.6889)
- **To change location**: Widget Studio → ⚙ Settings → Weather Location
- Enter your latitude/longitude → click **Refresh Weather Now**
- Refreshes every **20 minutes** (configurable in Settings → Refresh Intervals)

---

## Media Widget

Detects audio playing from:
- Spotify (desktop app)
- VLC
- Chrome / Edge (YouTube, SoundCloud)
- Windows Media Player
- Movies & TV
- Any app playing Windows audio

Uses `pycaw` to enumerate Windows audio sessions. Album art fetched from iTunes Search API (no auth needed).

Controls: Play/Pause, Next, Previous via `WM_APPCOMMAND`.

---

## Font System

### How it works
1. At startup, `WidgetRenderer` calls `_load_custom_fonts(assets_dir)`
2. Every `.ttf`/`.otf` in `assets/fonts/` is loaded into Qt's `QFontDatabase`
3. The `_font()` method reads `font_family` from each element, falls back to widget-level `style.font_family`, then `"Segoe UI"`
4. Every text renderer calls `_set_font(p, el)` — no hardcoded fonts

### Adding fonts
```
DeskFlow/
  assets/
    fonts/
      Inter-Regular.ttf     ← drop here
      Inter-Bold.ttf
      Roboto-Light.ttf
```
Then in Widget Studio → any text element → Font Family → type `Inter`.

---

## Project Structure

```
DeskFlow/
  main.py                   Entry point
  core/
    engine.py               Widget lifecycle orchestrator
    renderer.py             QPainter rendering engine (iOS 26 style)
    data_providers.py       Threaded data fetching + TTL cache
    widget_instance.py      Per-widget window + click handling
    app_controller.py       System tray + lifecycle
  editor/
    editor_window.py        Widget Studio (editor UI)
  widgets/
    media/
      media_controller.py   pycaw audio detection
      media_renderer.py     Media widget painter
      media_widget.py       Media widget window
    templates/
      default_widgets.py    22+ built-in widget templates
  plugins/
    spotify/                Spotify OAuth plugin
  utils/
    config.py               Persistent settings (APPDATA/DeskFlow/)
    json_store.py           Per-widget JSON persistence
    logger.py               Logging setup
  assets/
    fonts/                  Drop custom .ttf/.otf files here
  requirements.txt
```

---

## Settings

All configurable via Widget Studio → ⚙ Settings tab:

| Setting | Default | Notes |
|---------|---------|-------|
| Weather latitude | 33.7167 | Hasanabdal, Punjab |
| Weather longitude | 72.6889 | |
| Temperature unit | celsius | or fahrenheit |
| Weather refresh | 20 min | |
| News RSS URL | BBC News | Any RSS 2.0 feed |
| News refresh | 20 min | |
| Stocks refresh | 60 sec | |
| Crypto refresh | 30 sec | |

Settings saved to: `%APPDATA%\DeskFlow\settings.json`
