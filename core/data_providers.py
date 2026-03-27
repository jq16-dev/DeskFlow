"""
DataProviderRegistry — Thread-safe, TTL-cached data sources.
Covers: CPU, RAM, GPU, Disk, Network, Battery, Weather (Open-Meteo),
        Stocks (Yahoo Finance scrape), Crypto (CoinGecko),
        News (RSS), Forex (exchangerate.host), Time zones.
All heavy work runs on a background ThreadPoolExecutor.
UI thread is NEVER blocked.
"""

import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional
from collections import deque

logger = logging.getLogger("DeskFlow.Data")

_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="DF-Data")


# ─── Cache ────────────────────────────────────────────────────────────────────

class _Cache:
    def __init__(self):
        self._lock    = threading.Lock()
        self._data    : Dict[str, Any]   = {}
        self._expiry  : Dict[str, float] = {}
        self._history : Dict[str, deque] = {}

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if time.monotonic() < self._expiry.get(key, 0):
                return self._data.get(key)
        return None

    def last(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, value: Any, ttl: float):
        with self._lock:
            self._data[key]   = value
            self._expiry[key] = time.monotonic() + ttl
            if isinstance(value, (int, float)):
                if key not in self._history:
                    self._history[key] = deque(maxlen=60)
                self._history[key].append(float(value) / 100.0)

    def history(self, key: str) -> list:
        with self._lock:
            return list(self._history.get(key, []))


_cache   = _Cache()
_inflight: Dict[str, bool] = {}
_ilock    = threading.Lock()


# ─── Provider functions ───────────────────────────────────────────────────────

def _cpu(a):
    import psutil
    return psutil.cpu_percent(interval=0)

def _cpu_freq(a):
    import psutil
    f = psutil.cpu_freq()
    return round(f.current / 1000, 2) if f else 0.0   # GHz

def _cpu_temp(a):
    try:
        import psutil
        temps = psutil.sensors_temperatures()
        for key in ("coretemp", "k10temp", "cpu_thermal"):
            if key in temps and temps[key]:
                return round(temps[key][0].current, 1)
    except Exception:
        pass
    return 0.0

def _ram(a):
    import psutil
    return psutil.virtual_memory().percent

def _ram_used(a):
    import psutil
    v = psutil.virtual_memory()
    return round(v.used / 1024**3, 2)   # GB

def _ram_total(a):
    import psutil
    v = psutil.virtual_memory()
    return round(v.total / 1024**3, 1)

def _disk(a):
    import psutil
    return psutil.disk_usage(a.get("path", "/")).percent

def _disk_used(a):
    import psutil
    d = psutil.disk_usage(a.get("path", "/"))
    return round(d.used / 1024**3, 1)

def _disk_total(a):
    import psutil
    d = psutil.disk_usage(a.get("path", "/"))
    return round(d.total / 1024**3, 1)

def _net_speed(a):
    import psutil, time as t
    s1 = psutil.net_io_counters()
    t.sleep(0.5)
    s2 = psutil.net_io_counters()
    dl = round((s2.bytes_recv - s1.bytes_recv) / 0.5 / 1024, 1)  # KB/s
    ul = round((s2.bytes_sent - s1.bytes_sent) / 0.5 / 1024, 1)
    return {"download": dl, "upload": ul}

def _battery(a):
    import psutil
    b = psutil.sensors_battery()
    if not b:
        return {"percent": 100, "plugged": True, "remaining": "AC"}
    h, r = divmod(int(b.secsleft / 60) if b.secsleft > 0 else 0, 60)
    return {
        "percent": round(b.percent, 1),
        "plugged": b.power_plugged,
        "remaining": f"{h}h {r}m" if not b.power_plugged and b.secsleft > 0 else "Charging"
    }

def _gpu(a):
    try:
        import pynvml
        pynvml.nvmlInit()
        h   = pynvml.nvmlDeviceGetHandleByIndex(0)
        util = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
        mem  = pynvml.nvmlDeviceGetMemoryInfo(h)
        temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
        name = pynvml.nvmlDeviceGetName(h)
        return {
            "usage": float(util),
            "mem_used": round(mem.used / 1024**3, 1),
            "mem_total": round(mem.total / 1024**3, 1),
            "temp": temp,
            "name": name
        }
    except Exception:
        return {"usage": 0, "mem_used": 0, "mem_total": 0, "temp": 0, "name": "N/A"}

def _uptime(a):
    import psutil, time as t
    secs = int(t.time() - psutil.boot_time())
    h, rem = divmod(secs, 3600)
    m, _   = divmod(rem, 60)
    return f"{h}h {m}m"

def _hostname(a):
    import socket
    return socket.gethostname()

def _processes(a):
    import psutil
    return len(list(psutil.process_iter()))

# ── Weather ──

_WEATHER_CODES = {
    0:  ("☀️",  "Clear"),
    1:  ("🌤️", "Mostly Clear"),
    2:  ("⛅",  "Partly Cloudy"),
    3:  ("☁️",  "Overcast"),
    45: ("🌫️", "Foggy"),
    48: ("🌫️", "Icy Fog"),
    51: ("🌦️", "Light Drizzle"),
    53: ("🌦️", "Drizzle"),
    55: ("🌧️", "Heavy Drizzle"),
    61: ("🌧️", "Light Rain"),
    63: ("🌧️", "Rain"),
    65: ("🌧️", "Heavy Rain"),
    71: ("❄️",  "Light Snow"),
    73: ("❄️",  "Snow"),
    75: ("❄️",  "Heavy Snow"),
    80: ("🌦️", "Showers"),
    81: ("🌦️", "Heavy Showers"),
    82: ("⛈️",  "Violent Showers"),
    95: ("⛈️",  "Thunderstorm"),
    99: ("⛈️",  "Hail Storm"),
}

def _weather(a):
    try:
        import requests
        from datetime import datetime
        # Default: Hasanabdal, Punjab, Pakistan (33.7167 N, 72.6889 E)
        lat  = a.get("lat", 33.7167)
        lon  = a.get("lon", 72.6889)
        unit = a.get("unit", "celsius")
        city = a.get("city", "")

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current_weather=true"
            f"&hourly=relativehumidity_2m,apparent_temperature_2m,"
            f"precipitation_probability,windspeed_10m,uv_index,"
            f"weathercode,temperature_2m"
            f"&temperature_unit={unit}&windspeed_unit=kmh&timezone=auto"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        d  = r.json()
        cw = d.get("current_weather", {})
        code = cw.get("weathercode", 0)
        icon, desc = _WEATHER_CODES.get(code, ("🌡️", "Unknown"))

        # Find closest hourly index to current time
        hourly  = d.get("hourly", {})
        times   = hourly.get("time", [])
        now_str = datetime.now().strftime("%Y-%m-%dT%H:00")
        try:
            idx = times.index(now_str)
        except ValueError:
            idx = 0

        humidity = hourly.get("relativehumidity_2m", [None])[idx]
        feels    = hourly.get("apparent_temperature_2m", [None])[idx]
        if feels is None:
            feels = hourly.get("apparent_temperature", [None])[idx]
        precip   = hourly.get("precipitation_probability", [None])[idx]
        uv       = hourly.get("uv_index", [None])[idx]
        wind     = cw.get("windspeed", 0)
        symbol   = "°C" if unit == "celsius" else "°F"

        # Build next-5-hours forecast strip from hourly data
        hourly_temps  = hourly.get("temperature_2m", [])
        hourly_codes  = hourly.get("weathercode", [])
        forecast = []
        now_hour = datetime.now().hour
        for offset in range(0, 5):
            fi = idx + offset
            if fi < len(hourly_temps):
                h_code     = hourly_codes[fi] if fi < len(hourly_codes) else 0
                h_icon, _  = _WEATHER_CODES.get(h_code, ("☁", ""))
                h_temp     = hourly_temps[fi]
                # Format time label
                slot_hour  = (now_hour + offset) % 24
                label      = "Now" if offset == 0 else f"{slot_hour:02d}:00"
                forecast.append({
                    "time": label,
                    "icon": h_icon,
                    "temp": f"{round(h_temp)}{symbol}",
                })

        # Reverse-geocode city name if not provided
        if not city:
            try:
                geo_url = (
                    f"https://nominatim.openstreetmap.org/reverse"
                    f"?lat={lat}&lon={lon}&format=json&zoom=10"
                )
                gr = requests.get(geo_url, timeout=5,
                                  headers={"User-Agent": "DeskFlow/2026"})
                if gr.ok:
                    addr    = gr.json().get("address", {})
                    city    = (addr.get("city") or addr.get("town")
                               or addr.get("village") or addr.get("county") or "")
            except Exception:
                city = ""

        return {
            "temp":     f"{cw.get('temperature', '--')}{symbol}",
            "feels":    f"{feels}{symbol}" if feels is not None else "--",
            "desc":     desc,
            "icon":     icon,
            "humidity": f"{humidity}%" if humidity is not None else "--",
            "wind":     f"{wind} km/h",
            "precip":   f"{precip}%" if precip is not None else "--",
            "uv":       f"UV {uv}" if uv is not None else "",
            "code":     code,
            "lat":      lat,
            "lon":      lon,
            "city":     city,
            "forecast": forecast,   # list of {time, icon, temp} — 5 slots
        }
    except Exception as e:
        logger.debug(f"Weather error: {e}")
        return {"temp": "--", "feels": "--", "desc": "Unavailable", "icon": "☁️",
                "humidity": "--", "wind": "--", "precip": "--", "uv": "",
                "code": 0, "city": "", "forecast": []}

# ── Stocks / Crypto ──

def _stock(a):
    symbol = a.get("symbol", "AAPL")
    try:
        import requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=6)
        r.raise_for_status()
        meta = r.json()["chart"]["result"][0]["meta"]
        price   = round(meta.get("regularMarketPrice", 0), 2)
        prev    = round(meta.get("previousClose", price), 2)
        change  = round(price - prev, 2)
        pct     = round((change / prev) * 100, 2) if prev else 0
        return {
            "symbol":   symbol,
            "price":    price,
            "change":   change,
            "pct":      pct,
            "currency": meta.get("currency", "USD"),
            "up":       change >= 0,
        }
    except Exception as e:
        logger.debug(f"Stock [{symbol}] error: {e}")
        return {"symbol": symbol, "price": 0, "change": 0, "pct": 0, "currency": "USD", "up": True}

def _crypto(a):
    coin = a.get("coin", "bitcoin")
    vs   = a.get("vs_currency", "usd")
    try:
        import requests
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies={vs}&include_24hr_change=true"
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        data   = r.json().get(coin, {})
        price  = data.get(vs, 0)
        change = round(data.get(f"{vs}_24h_change", 0), 2)
        return {
            "coin":   coin.capitalize(),
            "price":  price,
            "change": change,
            "up":     change >= 0,
            "vs":     vs.upper(),
        }
    except Exception as e:
        logger.debug(f"Crypto [{coin}] error: {e}")
        return {"coin": coin.capitalize(), "price": 0, "change": 0, "up": True, "vs": vs.upper()}

def _forex(a):
    base   = a.get("base", "USD")
    target = a.get("target", "EUR")
    try:
        import requests
        url = f"https://open.er-api.com/v6/latest/{base}"
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        rates = r.json().get("rates", {})
        rate  = rates.get(target, 0)
        return {"base": base, "target": target, "rate": round(rate, 4)}
    except Exception as e:
        logger.debug(f"Forex error: {e}")
        return {"base": base, "target": target, "rate": 0}

# ── News ──

def _news_rss(a):
    feed_url = a.get("url", "https://feeds.bbci.co.uk/news/rss.xml")
    count    = a.get("count", 8)
    try:
        import requests
        import xml.etree.ElementTree as ET
        import html, re

        r = requests.get(feed_url, timeout=10,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root  = ET.fromstring(r.content)

        # Support both plain RSS and Atom namespaces
        NS = {
            "content": "http://purl.org/rss/1.0/modules/content/",
            "media":   "http://search.yahoo.com/mrss/",
            "dc":      "http://purl.org/dc/elements/1.1/",
        }

        def _clean(text: str) -> str:
            if not text:
                return ""
            # Strip HTML tags
            text = re.sub(r"<[^>]+>", " ", text)
            # Decode HTML entities
            text = html.unescape(text)
            # Collapse whitespace
            text = re.sub(r"\s+", " ", text).strip()
            return text

        items = []
        for item in root.findall(".//item")[:count]:
            title = _clean(item.findtext("title", ""))
            link  = item.findtext("link", "").strip()
            pub   = item.findtext("pubDate", "")[:16].strip()

            # Try several description fields, longest wins
            desc_candidates = [
                item.findtext("description", ""),
                item.findtext("{%s}encoded" % NS["content"], ""),
                item.findtext("summary", ""),
            ]
            desc = max((_clean(c) for c in desc_candidates), key=len)

            # If desc is just the title repeated, clear it
            if desc.lower().strip() == title.lower().strip():
                desc = ""

            if title:
                items.append({
                    "title": title,
                    "desc":  desc,
                    "link":  link,
                    "pub":   pub,
                })

        source = feed_url.split("/")[2].replace("www.", "").replace("feeds.", "")
        return {"items": items, "source": source}
    except Exception as e:
        logger.debug(f"RSS error: {e}")
        return {"items": [{"title": "News unavailable",
                           "desc": "", "link": "", "pub": ""}],
                "source": ""}

# ── Time zones ──

def _world_clock(a):
    import datetime
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        try:
            from backports.zoneinfo import ZoneInfo
        except ImportError:
            ZoneInfo = None

    results = []
    zones = a.get("zones", [
        {"tz": "America/New_York",  "label": "New York"},
        {"tz": "Europe/London",     "label": "London"},
        {"tz": "Asia/Tokyo",        "label": "Tokyo"},
    ])
    for z in zones:
        try:
            tz_name = z["tz"]
            if ZoneInfo:
                now = datetime.datetime.now(ZoneInfo(tz_name))
            else:
                now = datetime.datetime.utcnow()
            results.append({
                "label": z["label"],
                "time":  now.strftime("%H:%M"),
                "date":  now.strftime("%b %d"),
            })
        except Exception:
            results.append({"label": z.get("label", "?"), "time": "--:--", "date": ""})
    return {"clocks": results}



# ── Pomodoro ──

_pomo_state = {
    "mode": "idle",     # idle | work | break
    "remain_s": 25 * 60,
    "total_s":  25 * 60,
    "running":  False,
    "work_done": 0,
}
_pomo_lock = threading.Lock()

def _pomodoro(a):
    with _pomo_lock:
        s = dict(_pomo_state)
        if s["running"] and s["remain_s"] > 0:
            _pomo_state["remain_s"] -= 1
        elif s["running"] and s["remain_s"] <= 0:
            # Auto-switch
            if s["mode"] == "work":
                _pomo_state["mode"]     = "break"
                _pomo_state["total_s"]  = 5 * 60
                _pomo_state["remain_s"] = 5 * 60
                _pomo_state["work_done"] += 1
            else:
                _pomo_state["mode"]     = "work"
                _pomo_state["total_s"]  = 25 * 60
                _pomo_state["remain_s"] = 25 * 60
        return dict(_pomo_state)

def pomo_start():
    with _pomo_lock:
        if _pomo_state["mode"] == "idle":
            _pomo_state["mode"]    = "work"
            _pomo_state["remain_s"] = 25 * 60
            _pomo_state["total_s"]  = 25 * 60
        _pomo_state["running"] = True

def pomo_pause():
    with _pomo_lock:
        _pomo_state["running"] = False

def pomo_reset():
    with _pomo_lock:
        _pomo_state.update({"mode":"idle","remain_s":25*60,"total_s":25*60,"running":False})

# ─── Registry ─────────────────────────────────────────────────────────────────

_PROVIDERS: Dict[str, tuple] = {
    "cpu":          (_cpu,         1.0),
    "cpu_freq":     (_cpu_freq,    2.0),
    "cpu_temp":     (_cpu_temp,    3.0),
    "ram":          (_ram,         1.0),
    "ram_used":     (_ram_used,    1.0),
    "ram_total":    (_ram_total,   60.0),
    "disk":         (_disk,        5.0),
    "disk_used":    (_disk_used,   5.0),
    "disk_total":   (_disk_total,  60.0),
    "net_speed":    (_net_speed,   2.0),
    "battery":      (_battery,     10.0),
    "gpu":          (_gpu,         1.0),
    "uptime":       (_uptime,      30.0),
    "hostname":     (_hostname,    3600.0),
    "processes":    (_processes,   5.0),
    "weather":      (_weather,     1200.0),
    "stock":        (_stock,       60.0),
    "crypto":       (_crypto,      30.0),
    "forex":        (_forex,       300.0),
    "news":         (_news_rss,    1200.0),
    "world_clock":  (_world_clock, 30.0),
    "pomodoro":     (_pomodoro,    1.0),
}


class DataProviderRegistry:

    @staticmethod
    def _cache_key(key: str, args: dict) -> str:
        """Include relevant args in cache key to avoid cross-widget collisions."""
        if not args:
            return key
        # Only include args that affect the result (not display options)
        KEYED_ARGS = {
            "weather": ("lat", "lon", "unit"),
            "stock":   ("symbol",),
            "crypto":  ("coin", "vs_currency"),
            "forex":   ("base", "target"),
            "news":    ("url",),
            "disk":    ("path",),
        }
        sig_keys = KEYED_ARGS.get(key, ())
        if not sig_keys:
            return key
        sig = "|".join(f"{k}={args.get(k,'')}" for k in sig_keys if k in args)
        return f"{key}:{sig}" if sig else key

    @staticmethod
    def get(key: str, args: dict = None) -> Any:
        args = args or {}
        ckey = DataProviderRegistry._cache_key(key, args)

        cached = _cache.get(ckey)
        if cached is not None:
            return cached

        with _ilock:
            if _inflight.get(ckey):
                return _cache.last(ckey)
            _inflight[ckey] = True

        entry = _PROVIDERS.get(key)
        if not entry:
            with _ilock: _inflight[ckey] = False
            return None
        fn, ttl = entry

        def _run():
            try:
                val = fn(args)
                _cache.set(ckey, val, ttl)
            except Exception as e:
                logger.debug(f"Provider [{key}] error: {e}")
            finally:
                with _ilock: _inflight[ckey] = False

        _executor.submit(_run)
        return _cache.last(ckey)


    @staticmethod
    def register(key: str, fn: Callable, ttl: float = 1.0):
        _PROVIDERS[key] = (fn, ttl)

    @staticmethod
    def force_refresh(key: str, args: dict = None):
        """Force immediate background refresh (bypass TTL)."""
        args = args or {}
        ckey = DataProviderRegistry._cache_key(key, args)
        entry = _PROVIDERS.get(key)
        if not entry: return
        fn, ttl = entry
        def _run():
            try:
                _cache.set(ckey, fn(args), ttl)
            except Exception: pass
        _executor.submit(_run)

    @staticmethod
    def history(key: str, args: dict = None) -> list:
        ckey = DataProviderRegistry._cache_key(key, args or {})
        return _cache.history(ckey)
