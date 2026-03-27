"""
DeskFlow 2026 — Widget Templates
iOS 26 Premium Design System

All 22 templates follow:
  • Glass/frosted backgrounds  • Rounded corners 16-24px
  • Soft gradient fills        • Clean typography hierarchy
  • font_family / font_size / font_weight fully supported
  • time_format "12h" / "24h" on all clocks
  • Backward-compatible: missing settings fall back to sensible defaults
"""
import uuid

def _id():
    return str(uuid.uuid4())[:8]


# ─── Base builder (DeskFlow 2026 defaults) ────────────────────────────────────


def _weather_args(unit="celsius"):
    """Read weather location from AppConfig if available, else use defaults."""
    try:
        from utils.config import AppConfig
        cfg  = AppConfig()
        lat  = float(cfg.get("weather_lat", 33.7167))
        lon  = float(cfg.get("weather_lon", 72.6889))
        unit = cfg.get("weather_unit", unit)
        city = cfg.get("weather_city", "")
    except Exception:
        lat, lon, city = 33.7167, 72.6889, ""
    args = {"lat": lat, "lon": lon, "unit": unit}
    if city:
        args["city"] = city  # pre-set city so reverse geocode is skipped
    return args


def _base(name, x, y, w, h, interval=1000, layer="always_on_top",
          bg_type="glass", bg_color=None, r=20, border=1,
          border_c="#ffffff14", g_start=None, g_end=None,
          font_family="Segoe UI", **extra):
    style = {
        "background_type":  bg_type,
        "background_color": bg_color or [16, 16, 26, 218],
        "border_radius":    r,
        "border_width":     border,
        "border_color":     border_c,
        "font_family":      font_family,
    }
    if g_start:
        style["gradient_start"] = g_start
    if g_end:
        style["gradient_end"] = g_end
    d = {
        "name":            name,
        "position":        {"x": x, "y": y},
        "size":            {"width": w, "height": h},
        "update_interval": interval,
        "layer":           layer,
        "opacity":         1.0,
        "style":           style,
        "elements":        [],
    }
    d.update(extra)
    return d


def _el(etype, **kw):
    """Helper to create an element dict."""
    return {"id": _id(), "type": etype, **kw}


# ══════════════════════════════════════════════════════════════════════════════
# CLOCK WIDGETS
# ══════════════════════════════════════════════════════════════════════════════

def clock():
    """Premium 24h digital clock — large thin numerals."""
    w = _base("Clock", 80, 80, 268, 118, 1000,
              bg_type="gradient", g_start="#0e0e1c", g_end="#070710",
              border_c="#3b82f614", r=22)
    w["elements"] = [
        _el("clock", format="%H:%M", time_format="24h",
            x=0, y=4, width=268, height=72,
            font_size=58, font_weight="thin", font_family="Segoe UI",
            align="center", color="#f0f0ff"),
        _el("divider", x=20, y=78, width=228, height=1, color="#ffffff10"),
        _el("date", format="%A, %d %B", x=0, y=82, width=268, height=26,
            font_size=12, font_weight="light", font_family="Segoe UI",
            align="center", color="#5577aa"),
    ]
    return w


def clock_12h():
    """12-hour AM/PM clock — warm accent."""
    w = _base("Clock 12h", 80, 80, 268, 118, 1000,
              bg_type="gradient", g_start="#140e0a", g_end="#0a0805",
              border_c="#fb923c14", r=22)
    w["elements"] = [
        _el("clock", format="%I:%M", time_format="12h",
            x=0, y=4, width=210, height=72,
            font_size=56, font_weight="thin", font_family="Segoe UI",
            align="center", color="#fff7ed"),
        _el("clock", format="%p", time_format="12h",
            x=210, y=18, width=52, height=22,
            font_size=14, font_weight="medium", font_family="Segoe UI",
            align="left", color="#fb923c"),
        _el("date", format="%a · %b %d", x=0, y=82, width=268, height=26,
            font_size=12, align="center", color="#9a7a66"),
    ]
    return w


def minimal_clock():
    """Transparent minimal clock — numbers only, no background."""
    w = _base("Minimal Clock", 80, 80, 320, 96, 1000,
              bg_type="transparent", r=0, border=0)
    w["elements"] = [
        _el("clock", format="%H:%M", time_format="24h",
            x=0, y=0, width=320, height=68,
            font_size=60, font_weight="thin", font_family="Segoe UI",
            align="left", color="#ffffff"),
        _el("date", format="%A  ·  %B %d  ·  %Y",
            x=2, y=70, width=320, height=22,
            font_size=12, align="left", color="#555566"),
    ]
    return w


def analog_clock():
    """iOS-style circular analog clock with depth shading."""
    w = _base("Analog", 80, 220, 192, 192, 1000,
              bg_type="glass", bg_color=[10, 10, 22, 215],
              r=96, border_c="#ffffff12")
    w["elements"] = [
        _el("analog_clock", x=8, y=8, width=176, height=176,
            face_color=[12, 12, 22, 0],
            face_color_edge=[6, 6, 16, 0],
            hour_color="#ffffff", min_color="#e8e8f8",
            sec_color="#f87171", tick_color="#ffffff30",
            border_color="#ffffff18"),
    ]
    return w


def world_clock():
    """World clock — 3 cities with clean row layout."""
    w = _base("World Clock", 80, 80, 272, 124, 30000,
              bg_type="glass", bg_color=[14, 14, 24, 215], r=20)
    w["elements"] = [
        _el("text", text="WORLD CLOCK",
            x=16, y=10, width=240, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#334466", align="left"),
        _el("divider", x=16, y=26, width=240, height=1, color="#ffffff0c"),
        _el("world_clock", data_provider="world_clock",
            provider_args={"zones": [
                {"tz": "America/New_York", "label": "🗽 New York"},
                {"tz": "Europe/London",    "label": "🎡 London"},
                {"tz": "Asia/Karachi",     "label": "🌙 Karachi"},
            ]},
            x=16, y=30, width=240, height=84,
            font_size=16, font_weight="light", font_family="Segoe UI",
            color="#f0f0ff"),
    ]
    return w


def clock_with_seconds():
    """24h clock with large time + smaller seconds — premium style."""
    w = _base("Clock + Seconds", 80, 80, 268, 130, 1000,
              bg_type="gradient", g_start="#0a0a18", g_end="#060610",
              border_c="#818cf814", r=22)
    w["elements"] = [
        _el("clock", format="%H:%M", time_format="24h",
            x=0, y=8, width=268, height=68,
            font_size=54, font_weight="thin", font_family="Segoe UI",
            align="center", color="#f0f0ff",
            show_seconds=False),
        # Seconds displayed separately — smaller, muted
        _el("clock", format="%S", time_format="24h",
            x=0, y=12, width=268, height=68,
            font_size=18, font_weight="light", font_family="Segoe UI",
            align="right", color="#4455aa", show_seconds=False),
        _el("divider", x=20, y=82, width=228, height=1, color="#ffffff0c"),
        _el("date", format="%A, %d %B  ·  %Y",
            x=0, y=88, width=268, height=24,
            font_size=11, align="center", color="#445577"),
    ]
    return w


def clock_12h_seconds():
    """12h clock with seconds — warm amber tones."""
    w = _base("Clock 12h + Sec", 80, 80, 268, 130, 1000,
              bg_type="gradient", g_start="#130e06", g_end="#09060200",
              border_c="#f59e0b14", r=22)
    w["elements"] = [
        _el("clock", format="%I:%M", time_format="12h",
            x=0, y=8, width=200, height=68,
            font_size=52, font_weight="thin", font_family="Segoe UI",
            align="center", color="#fff7ed"),
        _el("clock", format="%S", time_format="12h",
            x=198, y=28, width=50, height=26,
            font_size=16, font_weight="light", font_family="Segoe UI",
            align="left", color="#78350f"),
        _el("clock", format="%p", time_format="12h",
            x=198, y=8, width=50, height=22,
            font_size=12, font_weight="medium", font_family="Segoe UI",
            align="left", color="#f59e0b"),
        _el("divider", x=20, y=82, width=228, height=1, color="#ffffff0c"),
        _el("date", format="%a · %b %d",
            x=0, y=88, width=268, height=24,
            font_size=11, align="center", color="#92400e"),
    ]
    return w


# ══════════════════════════════════════════════════════════════════════════════
# WEATHER
# ══════════════════════════════════════════════════════════════════════════════

def weather():
    """Live weather — Hasanabdal, Punjab, Pakistan."""
    w = _base("Weather", 360, 80, 296, 124, 1200000,
              bg_type="gradient", g_start="#071525", g_end="#0b1e38",
              border_c="#3b82f614", r=22)
    w["elements"] = [
        _el("weather", data_provider="weather",
            # Hasanabdal, Punjab, Pakistan (33.7167°N, 72.6889°E)
            provider_args=_weather_args(),
            x=12, y=8, width=272, height=108,
            temp_size=28, show_details=True,
            font_size=13, font_family="Segoe UI", color="#f0f0ff"),
    ]
    return w


def weather_full():
    """Weather + 5-slot hourly forecast strip — Hasanabdal, Punjab, Pakistan."""
    w = _base("Weather Full", 360, 80, 308, 210, 1200000,
              bg_type="gradient", g_start="#060f1e", g_end="#091833",
              border_c="#3b82f618", r=22)
    w["elements"] = [
        _el("weather", data_provider="weather",
            # Hasanabdal, Punjab, Pakistan (33.7167°N, 72.6889°E)
            provider_args=_weather_args(),
            x=12, y=8, width=284, height=100,
            temp_size=26, show_details=True,
            font_size=13, font_family="Segoe UI", color="#f0f0ff"),
        _el("divider", x=16, y=112, width=276, height=1, color="#ffffff0e"),
        _el("weather_forecast",
            x=8, y=118, width=292, height=82,
            slots=[
                {"time": "Now", "icon": "☀",  "temp": "24°"},
                {"time": "3PM", "icon": "⛅", "temp": "22°"},
                {"time": "6PM", "icon": "🌥", "temp": "19°"},
                {"time": "9PM", "icon": "🌙", "temp": "16°"},
                {"time": "Mid", "icon": "☁",  "temp": "14°"},
            ],
            font_size=12, font_family="Segoe UI", color="#d0d8f0"),
    ]
    return w


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM MONITOR
# ══════════════════════════════════════════════════════════════════════════════

def system_basic():
    """CPU / RAM / Disk bars — clean 3-row layout."""
    w = _base("System Basic", 80, 220, 298, 158, 1500,
              bg_type="glass", bg_color=[10, 10, 20, 220], r=20)

    def _stat_rows(label, prov, y, c1, c2):
        return [
            _el("label_value", label=label, id=_id(),
                data_provider=prov, unit="%",
                x=16, y=y, width=266, height=19,
                font_size=12, font_family="Segoe UI",
                label_color="#555577", color="#e8e8f8"),
            _el("progress", id=_id(), data_provider=prov,
                x=16, y=y + 21, width=266, height=7,
                fill_color=[c1, c2], track_color="#ffffff0e", radius=4),
        ]

    els = [
        _el("text", text="SYSTEM", x=16, y=10, width=200, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#333355", align="left"),
    ]
    els += _stat_rows("CPU",  "cpu",  28, "#3b82f6", "#22d3ee")
    els += _stat_rows("RAM",  "ram",  62, "#a78bfa", "#f472b6")
    els += _stat_rows("Disk", "disk", 96, "#f87171", "#fbbf24")
    els += [
        _el("divider", x=16, y=128, width=266, height=1, color="#ffffff0c"),
        _el("label_value", label="Uptime", id=_id(),
            data_provider="uptime",
            x=16, y=132, width=266, height=18,
            font_size=11, font_family="Segoe UI",
            label_color="#333355", color="#666688"),
    ]
    w["elements"] = els
    return w


def system_full():
    """Full system panel — CPU graph, RAM, Disk, GPU, Net, Battery."""
    w = _base("System Full", 80, 220, 304, 342, 1500,
              bg_type="glass", bg_color=[8, 8, 18, 222], r=22,
              border_c="#ffffff12")

    def stat_block(label, prov, y, c1, c2, with_graph=False):
        rows = [
            _el("label_value", label=label, id=_id(),
                data_provider=prov, unit="%",
                x=16, y=y, width=272, height=18,
                font_size=12, font_family="Segoe UI",
                label_color="#444466", color="#e8e8f8"),
            _el("progress", id=_id(), data_provider=prov,
                x=16, y=y + 20, width=272, height=6,
                fill_color=[c1, c2], track_color="#ffffff0d", radius=3),
        ]
        if with_graph:
            rows.append(_el("bar_graph", id=_id(), data_provider=prov,
                            x=16, y=y + 28, width=272, height=22,
                            fill_color=c1 + "88", bars=30, heat=False))
        return rows

    els = [
        _el("text", text="SYSTEM MONITOR", x=16, y=10, width=272, height=14,
            font_size=9, font_weight="bold", font_family="Segoe UI",
            color="#222244", align="left"),
        _el("label_value", label="", id=_id(), data_provider="hostname",
            x=16, y=10, width=272, height=14,
            font_size=9, font_family="Segoe UI",
            label_color="#222244", color="#444466", align="right"),
    ]
    els += stat_block("CPU",  "cpu",  28, "#3b82f6", "#22d3ee", with_graph=True)
    els += stat_block("RAM",  "ram",  88, "#a78bfa", "#f472b6")
    els += stat_block("DISK", "disk", 118, "#f87171", "#fbbf24")
    els += [
        _el("divider", x=16, y=148, width=272, height=1, color="#ffffff0c"),
        _el("network", id=_id(), data_provider="net_speed",
            x=16, y=152, width=272, height=24,
            font_family="Segoe UI"),
        _el("divider", x=16, y=180, width=272, height=1, color="#ffffff0c"),
        _el("battery", id=_id(), data_provider="battery",
            x=16, y=184, width=272, height=28,
            font_family="Segoe UI"),
        _el("divider", x=16, y=216, width=272, height=1, color="#ffffff0c"),
        _el("label_value", label="GPU", id=_id(), data_provider="gpu", unit="%",
            x=16, y=220, width=272, height=18,
            font_size=11, font_family="Segoe UI",
            label_color="#444466", color="#d0d0e8"),
        _el("label_value", label="CPU Temp", id=_id(), data_provider="cpu_temp", unit="°C",
            x=16, y=242, width=272, height=18,
            font_size=11, font_family="Segoe UI",
            label_color="#444466", color="#d0d0e8"),
        _el("divider", x=16, y=264, width=272, height=1, color="#ffffff0c"),
        _el("label_value", label="Uptime", id=_id(), data_provider="uptime",
            x=16, y=268, width=272, height=18,
            font_size=11, font_family="Segoe UI",
            label_color="#444466", color="#666688"),
        _el("label_value", label="Processes", id=_id(), data_provider="processes",
            x=16, y=290, width=272, height=18,
            font_size=11, font_family="Segoe UI",
            label_color="#444466", color="#666688"),
        _el("label_value", label="RAM Used", id=_id(), data_provider="ram_used", unit=" GB",
            x=16, y=312, width=272, height=18,
            font_size=11, font_family="Segoe UI",
            label_color="#444466", color="#666688"),
    ]
    w["elements"] = els
    return w


def neon_stats():
    """3 ring gauges + sparkline — colourful premium dashboard block."""
    w = _base("Neon Stats", 396, 220, 272, 212, 1500,
              bg_type="solid", bg_color=[5, 5, 12, 255],
              r=22, border_c="#ffffff08")
    w["elements"] = [
        _el("text", text="PERFORMANCE", x=0, y=10, width=272, height=15,
            font_size=9, font_weight="bold", font_family="Segoe UI",
            color="#1a1a2e", align="center"),
        # Rings row
        _el("ring", id=_id(), data_provider="cpu",
            x=12, y=28, width=74, height=74,
            thickness=7, fill_color="#3b82f6",
            show_value=True, font_size=14,
            font_family="Segoe UI", color="#93c5fd"),
        _el("ring", id=_id(), data_provider="ram",
            x=99, y=28, width=74, height=74,
            thickness=7, fill_color="#a78bfa",
            show_value=True, font_size=14,
            font_family="Segoe UI", color="#c4b5fd"),
        _el("ring", id=_id(), data_provider="disk",
            x=186, y=28, width=74, height=74,
            thickness=7, fill_color="#f472b6",
            show_value=True, font_size=14,
            font_family="Segoe UI", color="#fbcfe8"),
        # Labels
        _el("text", text="CPU",  x=12,  y=102, width=74,  height=13,
            font_size=9, align="center", color="#3b82f6"),
        _el("text", text="RAM",  x=99,  y=102, width=74,  height=13,
            font_size=9, align="center", color="#a78bfa"),
        _el("text", text="DISK", x=186, y=102, width=74,  height=13,
            font_size=9, align="center", color="#f472b6"),
        _el("divider", x=16, y=118, width=240, height=1, color="#ffffff08"),
        # CPU sparkline
        _el("sparkline", id=_id(), data_provider="cpu",
            x=16, y=124, width=240, height=36,
            line_color="#3b82f6", fill_color=[59, 130, 246, 20],
            font_size=12, font_family="Segoe UI",
            color="#93c5fd", unit="%"),
        # Network
        _el("network", id=_id(), data_provider="net_speed",
            x=16, y=166, width=240, height=22,
            font_family="Segoe UI"),
        # Uptime
        _el("label_value", label="Uptime", id=_id(),
            data_provider="uptime",
            x=16, y=190, width=240, height=17,
            font_size=10, font_family="Segoe UI",
            label_color="#222240", color="#444466"),
    ]
    return w


# ══════════════════════════════════════════════════════════════════════════════
# FINANCE
# ══════════════════════════════════════════════════════════════════════════════

def finance_stocks():
    """4 live stock tickers — clean list layout."""
    w = _base("Stocks", 684, 80, 294, 244, 60000,
              bg_type="gradient", g_start="#08100e", g_end="#0b1812",
              border_c="#22c55e14", r=22)
    els = [
        _el("text", text="STOCKS",
            x=16, y=10, width=262, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#14321e", align="left"),
    ]
    for sym, y in [("AAPL", 28), ("MSFT", 86), ("GOOGL", 144), ("NVDA", 202)]:
        els.append(_el("stock", id=_id(), data_provider="stock",
                       provider_args={"symbol": sym},
                       x=16, y=y, width=262, height=50,
                       font_size=16, font_family="Segoe UI"))
        if y < 202:
            els.append(_el("divider", x=16, y=y + 52, width=262, height=1,
                           color="#ffffff08"))
    w["elements"] = els
    return w


def finance_crypto():
    """Bitcoin + Ethereum price cards."""
    w = _base("Crypto", 684, 80, 294, 192, 30000,
              bg_type="gradient", g_start="#090910", g_end="#100918",
              border_c="#f7931a18", r=22)
    w["elements"] = [
        _el("text", text="CRYPTO",
            x=16, y=10, width=262, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#2a180a", align="left"),
        _el("crypto", id=_id(), data_provider="crypto",
            provider_args={"coin": "bitcoin", "vs_currency": "usd"},
            x=16, y=28, width=262, height=58,
            font_size=15, font_family="Segoe UI"),
        _el("divider", x=16, y=88, width=262, height=1, color="#ffffff08"),
        _el("crypto", id=_id(), data_provider="crypto",
            provider_args={"coin": "ethereum", "vs_currency": "usd"},
            x=16, y=94, width=262, height=58,
            font_size=15, font_family="Segoe UI"),
        _el("divider", x=16, y=154, width=262, height=1, color="#ffffff08"),
        _el("label_value", label="Updated", id=_id(),
            x=16, y=158, width=262, height=26,
            font_size=10, font_family="Segoe UI",
            label_color="#2a180a", color="#554433"),
    ]
    return w


def finance_forex():
    """5 currency pairs — compact row layout."""
    w = _base("Forex", 684, 80, 276, 186, 300000,
              bg_type="gradient", g_start="#081006", g_end="#0c1a0a",
              border_c="#22c55e18", r=22)
    els = [
        _el("text", text="FOREX",
            x=16, y=10, width=244, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#0a1a08", align="left"),
    ]
    pairs = [
        ("USD", "EUR",  28),
        ("USD", "GBP",  62),
        ("USD", "PKR",  96),
        ("USD", "JPY", 130),
        ("EUR", "USD", 164),
    ]
    for base, target, y in pairs:
        els.append(_el("forex", id=_id(), data_provider="forex",
                       provider_args={"base": base, "target": target},
                       x=16, y=y, width=244, height=28,
                       font_size=13, font_family="Segoe UI"))
        if y < 164:
            els.append(_el("divider", x=16, y=y + 30, width=244, height=1,
                           color="#ffffff08"))
    w["elements"] = els
    return w


# ══════════════════════════════════════════════════════════════════════════════
# NEWS & MEDIA
# ══════════════════════════════════════════════════════════════════════════════

def news_feed():
    """BBC RSS feed — 6 headline rows with accent dots."""
    w = _base("News Feed", 80, 460, 338, 196, 300000,
              bg_type="glass", bg_color=[10, 10, 20, 218], r=20)
    w["elements"] = [
        _el("news", id=_id(), data_provider="news",
            provider_args={
                "url":   "https://feeds.bbci.co.uk/news/rss.xml",
                "count": 6,
            },
            x=12, y=8, width=314, height=180,
            font_size=11, row_height=28,
            font_family="Segoe UI", color="#e8e8f8",
            accent="#3b82f6"),
    ]
    return w


def media_now_playing():
    """Full media now-playing widget — any app via Windows SMTC."""
    w = _base("Media Now Playing", 80, 460, 376, 160, 2000,
              bg_type="glass", bg_color=[10, 10, 20, 228], r=22,
              border_c="#ffffff10")
    w["widget_type"]    = "media"
    w["show_art"]       = True
    w["show_controls"]  = True
    w["elements"] = [
        _el("media_now_playing",
            x=0, y=0, width=376, height=144,
            show_art=True, show_controls=True,
            font_size=13, font_family="Segoe UI",
            border_radius=22),
    ]
    return w


def media_compact():
    """Slim media bar — title + controls, no album art."""
    w = _base("Media Compact", 80, 620, 350, 80, 2000,
              bg_type="glass", bg_color=[10, 10, 20, 218], r=18,
              border_c="#ffffff0e")
    w["widget_type"]   = "media"
    w["show_art"]      = False
    w["show_controls"] = True
    w["elements"] = [
        _el("media_now_playing",
            x=0, y=0, width=350, height=80,
            show_art=False, show_controls=True,
            font_size=12, font_family="Segoe UI",
            border_radius=18),
    ]
    return w


# ══════════════════════════════════════════════════════════════════════════════
# CALENDAR / PRODUCTIVITY
# ══════════════════════════════════════════════════════════════════════════════

def calendar():
    """Mini month calendar — today highlighted with accent dot."""
    w = _base("Calendar", 378, 374, 254, 218, 60000,
              bg_type="glass", bg_color=[10, 10, 22, 215], r=22)
    w["elements"] = [
        _el("calendar_mini", x=10, y=8, width=234, height=202,
            today_color="#3b82f6",
            font_family="Segoe UI", color="#e8e8f8",
            header_color="#6688aa"),
    ]
    return w


def todo():
    """Checklist widget — done items checked in green."""
    w = _base("To-Do", 642, 374, 276, 234, 60000,
              bg_type="glass", bg_color=[10, 10, 22, 215], r=22)
    w["elements"] = [
        _el("text", text="TODAY", x=16, y=10, width=244, height=15,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#333355", align="left"),
        _el("divider", x=16, y=27, width=244, height=1, color="#ffffff0c"),
        _el("todo_list", x=16, y=32, width=244, height=194,
            items=[
                {"text": "O Level Physics revision",   "done": False},
                {"text": "Math 4024 Paper 2",          "done": False},
                {"text": "Global Perspectives report", "done": True},
                {"text": "Haider Wing duty check",     "done": False},
                {"text": "Group project meeting",      "done": False},
                {"text": "Evening sports practice",    "done": True},
            ],
            font_size=12, row_height=30,
            font_family="Segoe UI", color="#e8e8f8"),
    ]
    return w


def countdown_widget():
    """Days countdown to target date — large number with label."""
    import datetime
    target = (datetime.datetime.now().replace(day=1)
              + datetime.timedelta(days=32)).replace(day=1)
    w = _base("Countdown", 80, 80, 210, 116, 60000,
              bg_type="glass", bg_color=[10, 10, 22, 215], r=22)
    w["elements"] = [
        _el("countdown",
            target_date=target.strftime("%Y-%m-%d"),
            label="NEXT MILESTONE",
            x=0, y=0, width=210, height=116,
            font_size=48, font_weight="thin",
            font_family="Segoe UI",
            color="#ffffff", label_color="#444466", sub_color="#333355"),
    ]
    return w


def shortcuts_panel():
    """6-button app launcher grid — glassmorphic pill buttons."""
    w = _base("Shortcuts", 80, 80, 290, 148, 0,
              bg_type="glass", bg_color=[10, 10, 22, 215], r=22)
    BTNS = [
        ("🌐", "Browser",  "#3b82f6", "https://google.com"),
        ("💻", "Terminal", "#22d3ee", "cmd.exe"),
        ("📁", "Files",    "#fbbf24", "explorer.exe"),
        ("⚙",  "Settings", "#a78bfa", "ms-settings:"),
        ("📝", "Notepad",  "#4ade80", "notepad.exe"),
        ("🎵", "Music",    "#f472b6", "https://open.spotify.com"),
    ]
    els = [
        _el("text", text="SHORTCUTS",
            x=16, y=8, width=258, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#333355", align="left"),
    ]
    for i, (icon, label, color, target) in enumerate(BTNS):
        col = i % 3
        row = i // 3
        bx  = 16 + col * 88
        by  = 26 + row * 56
        els.append(_el("shortcut_btn",
                       icon=icon, label=label, color=color,
                       app=target, url=target,
                       icon_color="#ffffff", radius=12,
                       font_size=10, font_family="Segoe UI",
                       x=bx, y=by, width=82, height=50))
    w["elements"] = els
    return w


def notification_feed():
    """Status / notification pills stack."""
    w = _base("Notifications", 80, 80, 318, 152, 5000,
              bg_type="glass", bg_color=[10, 10, 22, 215], r=22)
    INFO = [
        ("System up to date",    "#3b82f6", 28),
        ("CPU nominal",          "#22c55e", 62),
        ("Network connected",    "#22d3ee", 96),
        ("DeskFlow 2026 active", "#a78bfa", 130),
    ]
    els = [
        _el("text", text="NOTIFICATIONS",
            x=16, y=8, width=286, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#333355", align="left"),
    ]
    for msg, accent, y in INFO:
        els.append(_el("notification_bar",
                       items=[msg], accent=accent,
                       x=16, y=y, width=286, height=26,
                       font_size=11, font_family="Segoe UI",
                       color="#c8c8e0"))
    w["elements"] = els
    return w


def battery_net():
    """Battery + network speeds — compact dual-row card."""
    w = _base("Power & Network", 80, 628, 298, 112, 5000,
              bg_type="glass", bg_color=[8, 8, 18, 218], r=20)
    w["elements"] = [
        _el("text", text="POWER & NETWORK",
            x=16, y=10, width=266, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#333355", align="left"),
        _el("battery", id=_id(), data_provider="battery",
            x=16, y=28, width=266, height=30,
            font_family="Segoe UI"),
        _el("divider", x=16, y=62, width=266, height=1, color="#ffffff0c"),
        _el("network", id=_id(), data_provider="net_speed",
            x=16, y=68, width=266, height=30,
            font_family="Segoe UI"),
    ]
    return w




# ── Notes Widget ─────────────────────────────────────────────────────────────

def notes_widget():
    """Sticky-note style notes widget."""
    w = _base("Notes", 80, 80, 282, 200, 0,
              bg_type="glass", bg_color=[22, 20, 10, 215], r=18,
              border_c="#fde68a18")
    w["elements"] = [
        _el("notes",
            title="My Notes",
            text="Add your notes here\nThey persist between sessions\n\n• Idea 1\n• Idea 2",
            x=0, y=0, width=282, height=200,
            font_size=12, font_family="Segoe UI",
            color="#e8e8cc", title_color="#fde68a",
            note_color="#fefce8"),
    ]
    return w


# ── Pomodoro Timer ────────────────────────────────────────────────────────────

def pomodoro_widget():
    """Pomodoro 25/5 timer widget."""
    w = _base("Pomodoro", 80, 80, 200, 200, 1000,
              bg_type="glass", bg_color=[14, 10, 10, 215], r=100,
              border_c="#f8717118")
    w["elements"] = [
        _el("pomodoro", id=_id(), data_provider="pomodoro",
            x=0, y=0, width=200, height=200,
            font_size=28, font_family="Segoe UI",
            color="#ffffff"),
    ]
    return w


# ── CPU Graph ────────────────────────────────────────────────────────────────

def cpu_graph():
    """Dedicated CPU history bar graph."""
    w = _base("CPU Graph", 80, 80, 298, 136, 1500,
              bg_type="glass", bg_color=[8, 10, 18, 218], r=20)
    w["elements"] = [
        _el("text", text="CPU USAGE",
            x=16, y=8, width=266, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#1a2240", align="left"),
        _el("label_value", label="", id=_id(), data_provider="cpu", unit="%",
            x=200, y=8, width=82, height=14,
            font_size=9, font_family="Segoe UI",
            label_color="#1a2240", color="#3b82f6"),
        _el("bar_graph", id=_id(), data_provider="cpu",
            x=12, y=26, width=274, height=68,
            fill_color="#3b82f6", bars=32, heat=True),
        _el("sparkline", id=_id(), data_provider="cpu",
            x=12, y=98, width=274, height=28,
            line_color="#3b82f6", font_size=11,
            font_family="Segoe UI", color="#93c5fd", unit="%"),
    ]
    return w


# ── RAM Graph ────────────────────────────────────────────────────────────────

def ram_graph():
    """RAM usage with history graph."""
    w = _base("RAM Graph", 80, 80, 298, 136, 1500,
              bg_type="glass", bg_color=[10, 8, 18, 218], r=20)
    w["elements"] = [
        _el("text", text="MEMORY",
            x=16, y=8, width=200, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#1a1030", align="left"),
        _el("label_value", label="", id=_id(), data_provider="ram", unit="%",
            x=200, y=8, width=82, height=14,
            font_size=9, font_family="Segoe UI",
            label_color="#1a1030", color="#a78bfa"),
        _el("line_graph", id=_id(), data_provider="ram",
            x=12, y=26, width=274, height=70,
            line_color="#a78bfa", fill_color=[167, 139, 250, 30]),
        _el("label_value", label="Used", id=_id(), data_provider="ram_used", unit=" GB",
            x=12, y=100, width=134, height=26,
            font_size=11, font_family="Segoe UI",
            label_color="#442266", color="#c4b5fd"),
        _el("label_value", label="Total", id=_id(), data_provider="ram_total", unit=" GB",
            x=150, y=100, width=134, height=26,
            font_size=11, font_family="Segoe UI",
            label_color="#442266", color="#c4b5fd"),
    ]
    return w


# ── Network Monitor ───────────────────────────────────────────────────────────

def network_monitor():
    """Network speed monitor with history sparklines."""
    w = _base("Network", 80, 80, 298, 136, 2000,
              bg_type="glass", bg_color=[6, 12, 14, 218], r=20)
    w["elements"] = [
        _el("text", text="NETWORK",
            x=16, y=8, width=266, height=14,
            font_size=9, font_weight="bold",
            font_family="Segoe UI", color="#0a1820", align="left"),
        _el("network", id=_id(), data_provider="net_speed",
            x=12, y=24, width=274, height=30,
            font_size=13, font_family="Segoe UI"),
        _el("divider", x=16, y=58, width=266, height=1, color="#ffffff0c"),
        _el("label_value", label="Host", id=_id(), data_provider="hostname",
            x=16, y=62, width=266, height=20,
            font_size=10, font_family="Segoe UI",
            label_color="#0a1820", color="#666688"),
        _el("label_value", label="Processes", id=_id(), data_provider="processes",
            x=16, y=84, width=266, height=20,
            font_size=10, font_family="Segoe UI",
            label_color="#0a1820", color="#666688"),
        _el("label_value", label="Uptime", id=_id(), data_provider="uptime",
            x=16, y=106, width=266, height=20,
            font_size=10, font_family="Segoe UI",
            label_color="#0a1820", color="#666688"),
    ]
    return w

# ── Blank ─────────────────────────────────────────────────────────────────────

def blank_widget():
    return _base("New Widget", 200, 200, 276, 120, 1000,
                 bg_type="glass", bg_color=[14, 14, 28, 215],
                 border_c="#3b82f620", r=22)


# ── Template Registry ─────────────────────────────────────────────────────────

TEMPLATES = {
    "clock":              clock,
    "clock_12h":          clock_12h,
    "clock_with_seconds": clock_with_seconds,
    "clock_12h_seconds":  clock_12h_seconds,
    "minimal_clock":      minimal_clock,
    "analog_clock":       analog_clock,
    "world_clock":        world_clock,
    "weather":           weather,
    "weather_full":      weather_full,
    "system_basic":      system_basic,
    "system_full":       system_full,
    "neon_stats":        neon_stats,
    "finance_stocks":    finance_stocks,
    "finance_crypto":    finance_crypto,
    "finance_forex":     finance_forex,
    "news_feed":         news_feed,
    "media_now_playing": media_now_playing,
    "media_compact":     media_compact,
    "calendar":          calendar,
    "todo":              todo,
    "countdown":         countdown_widget,
    "shortcuts_panel":   shortcuts_panel,
    "notification_feed": notification_feed,
    "battery_net":       battery_net,
    "notes":             notes_widget,
    "pomodoro":          pomodoro_widget,
    "cpu_graph":         cpu_graph,
    "ram_graph":         ram_graph,
    "network_monitor":   network_monitor,
}


def get_template(name: str) -> dict:
    fn = TEMPLATES.get(name)
    return fn() if fn else blank_widget()
