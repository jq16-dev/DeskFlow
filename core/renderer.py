"""
DeskFlow 2026 Renderer — iOS 26 Premium Widget Rendering Engine.

Design system:
  • Rounded corners 16-24px
  • Glass / frosted backgrounds with subtle inner highlights
  • Soft depth shadows (multi-pass)
  • Smooth gradients — NOT flat colours
  • SF Pro / Segoe UI typography with proper hierarchy
  • Dark-first, premium finish
  • Consistent spacing grid (8px)
  • Accent colours per-widget with alpha blends

Every element renderer enforces the DeskFlow design system.
font_family / font_size / font_weight respected on all text elements.
time_format "12h" / "24h" on all clock elements.
"""

import math
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QFont, QFontMetrics, QFontDatabase,
    QLinearGradient, QRadialGradient, QConicalGradient,
    QPen, QBrush, QPixmap, QPaintEvent, QImage
)

from core.data_providers import DataProviderRegistry

logger = logging.getLogger("DeskFlow.Renderer")

# ─── Design tokens ────────────────────────────────────────────────────────────

class DS:
    """DeskFlow 2026 Design System tokens."""
    # Background glass
    BG_GLASS       = QColor(18, 18, 28, 220)
    BG_GLASS_LIGHT = QColor(255, 255, 255, 18)  # inner highlight
    BG_CARD        = QColor(14, 14, 22, 235)

    # Typography hierarchy
    TEXT_PRIMARY   = QColor(240, 240, 250)
    TEXT_SECONDARY = QColor(155, 155, 175)
    TEXT_TERTIARY  = QColor(75,  75,  95)
    TEXT_ACCENT    = QColor(100, 160, 255)

    # Status colours
    GREEN  = QColor(52,  211, 153)
    YELLOW = QColor(251, 191, 36)
    RED    = QColor(248, 113, 113)
    BLUE   = QColor(96,  165, 250)
    PURPLE = QColor(167, 139, 250)
    PINK   = QColor(244, 114, 182)
    CYAN   = QColor(34,  211, 238)

    # Radii
    R_CARD  = 20
    R_INNER = 12
    R_PILL  = 100

    # Spacing
    PAD = 16


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _c(v, default="#ffffff") -> QColor:
    if isinstance(v, str):
        return QColor(v)
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        a = v[3] if len(v) == 4 else 255
        return QColor(int(v[0]), int(v[1]), int(v[2]), int(a))
    return QColor(default)


def _align(s: str) -> Qt.AlignmentFlag:
    h = {"left": Qt.AlignLeft, "center": Qt.AlignHCenter, "right": Qt.AlignRight}
    return h.get(s, Qt.AlignLeft) | Qt.AlignVCenter


def _fmt_bytes(kb: float) -> str:
    if kb >= 1024:
        return f"{kb/1024:.1f} MB/s"
    return f"{kb:.0f} KB/s"


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(
        int(c1.red()   + (c2.red()   - c1.red())   * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue()  + (c2.blue()  - c1.blue())  * t),
    )


def _alpha(c: QColor, a: int) -> QColor:
    r = QColor(c)
    r.setAlpha(a)
    return r


def _draw_pill_label(p: QPainter, rect: QRectF, text: str, bg: QColor, fg: QColor,
                      font_size=9, font_family="Segoe UI"):
    """Draw a small pill / badge label."""
    f  = QFont(font_family, font_size, QFont.Bold)
    fm = QFontMetrics(f)
    tw = fm.horizontalAdvance(text) + 14
    th = max(18, fm.height() + 6)
    pr = QRectF(rect.x(), rect.center().y() - th/2, tw, th)
    pp = QPainterPath()
    pp.addRoundedRect(pr, th/2, th/2)
    p.fillPath(pp, QBrush(bg))
    p.setFont(f)
    p.setPen(fg)
    p.drawText(pr, Qt.AlignCenter, text)


def _value_heat(val: float) -> QColor:
    """0-100 → green→yellow→red."""
    if val < 50:
        return _lerp_color(DS.GREEN, DS.YELLOW, val / 50)
    return _lerp_color(DS.YELLOW, DS.RED, (val - 50) / 50)


# ─── Core renderer ────────────────────────────────────────────────────────────

# ── Custom font registry (loaded once at startup) ─────────────────────────────
_custom_fonts_loaded = False

def _load_custom_fonts(assets_dir):
    """
    Load all .ttf and .otf fonts from assets/fonts/ into QFontDatabase.
    Must be called after QApplication is created.
    Call once; subsequent calls are no-ops.
    """
    global _custom_fonts_loaded
    if _custom_fonts_loaded:
        return
    _custom_fonts_loaded = True
    if not assets_dir:
        return
    from pathlib import Path
    fonts_dir = Path(assets_dir) / "fonts"
    if not fonts_dir.exists():
        logger.debug("No assets/fonts/ directory — only system fonts available")
        return
    loaded = 0
    for ext in ("*.ttf", "*.otf", "*.TTF", "*.OTF"):
        for fp in fonts_dir.glob(ext):
            fid = QFontDatabase.addApplicationFont(str(fp))
            if fid >= 0:
                families = QFontDatabase.applicationFontFamilies(fid)
                logger.info(f"Loaded font: {fp.name} → {families}")
                loaded += 1
            else:
                logger.warning(f"Failed to load font: {fp}")
    logger.info(f"Custom fonts loaded: {loaded}")


class WidgetRenderer:
    def __init__(self, widget_def: dict, config=None):
        self.config = config
        self._cache: Dict[str, Any] = {}
        self._art_cache: Dict[str, QPixmap] = {}
        # Load custom fonts on first renderer creation
        if config and hasattr(config, "assets_dir"):
            _load_custom_fonts(config.assets_dir)
        self.reload(widget_def)

    def reload(self, widget_def: dict):
        self.wdef     = widget_def
        self.style    = widget_def.get("style", {})
        self.elements = widget_def.get("elements", [])
        self._cache   = {}

    def refresh_data(self):
        for el in self.elements:
            key  = el.get("data_provider")
            args = el.get("provider_args", {})
            eid  = el.get("id", key or "")
            if not key:
                continue
            val = DataProviderRegistry.get(key, args)
            if val is not None:
                self._cache[eid]           = val
                self._cache[eid + "_hist"] = DataProviderRegistry.history(key, args)

    # ── Public paint entry ──────────────────────────────────────────────────

    def paint(self, widget: QWidget, event: QPaintEvent):
        p = QPainter(widget)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        self.paint_to_painter(p, widget.width(), widget.height())
        p.end()

    def paint_to_painter(self, p: QPainter, w: int, h: int):
        rect = QRectF(0, 0, w, h)
        self._bg(p, rect)
        for el in self.elements:
            p.save()
            p.setOpacity(el.get("opacity", 1.0))
            try:
                self._dispatch(p, el, w, h)
            except Exception as e:
                logger.debug(f"Element render error [{el.get('type')}]: {e}")
            p.restore()

    # ── iOS 26 Background ────────────────────────────────────────────────────

    def _bg(self, p: QPainter, rect: QRectF):
        s = self.style
        r = s.get("border_radius", DS.R_CARD)

        # Soft outer shadow (2 passes for depth)
        for sh_offset, sh_alpha in [(6, 40), (3, 25)]:
            sh_path = QPainterPath()
            sh_path.addRoundedRect(
                rect.adjusted(sh_offset, sh_offset, sh_offset, sh_offset), r, r)
            p.fillPath(sh_path, QColor(0, 0, 0, sh_alpha))

        path = QPainterPath()
        path.addRoundedRect(rect, r, r)
        p.setClipPath(path)

        btype = s.get("background_type", "glass")

        if btype == "transparent":
            pass

        elif btype == "glass":
            # Main glass fill
            gc = _c(s.get("background_color", [18, 18, 28, 210]))
            p.fillPath(path, QBrush(gc))

            # Inner top highlight (frosted glass shimmer)
            hi_path = QPainterPath()
            hi_path.addRoundedRect(
                QRectF(rect.x() + 1, rect.y() + 1,
                       rect.width() - 2, rect.height() * 0.38), r - 1, r - 1)
            p.fillPath(hi_path, QBrush(QColor(255, 255, 255, 14)))

            # Bottom vignette
            v_grad = QLinearGradient(rect.bottomLeft(), rect.topLeft())
            v_grad.setColorAt(0, QColor(0, 0, 0, 30))
            v_grad.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillPath(path, QBrush(v_grad))

        elif btype == "gradient":
            g = QLinearGradient(rect.topLeft(), rect.bottomRight())
            g.setColorAt(0, _c(s.get("gradient_start", "#1a1a2e")))
            g.setColorAt(1, _c(s.get("gradient_end",   "#0f0f1e")))
            if s.get("gradient_mid"):
                g.setColorAt(0.5, _c(s["gradient_mid"]))
            p.fillPath(path, QBrush(g))
            # Top glass sheen
            sh = QLinearGradient(rect.topLeft(), QPointF(rect.x(), rect.y() + rect.height() * 0.4))
            sh.setColorAt(0, QColor(255, 255, 255, 16))
            sh.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillPath(path, QBrush(sh))

        elif btype == "radial":
            g = QRadialGradient(rect.center(), max(rect.width(), rect.height()) / 2)
            g.setColorAt(0, _c(s.get("gradient_start", "#1a2a3e")))
            g.setColorAt(1, _c(s.get("gradient_end",   "#0a0a1a")))
            p.fillPath(path, QBrush(g))

        elif btype == "frosted":
            # Extra-premium frosted effect
            base = _c(s.get("background_color", [20, 20, 35, 200]))
            p.fillPath(path, QBrush(base))
            noise_g = QRadialGradient(rect.center(), rect.width() * 0.7)
            noise_g.setColorAt(0, QColor(255, 255, 255, 8))
            noise_g.setColorAt(0.5, QColor(255, 255, 255, 4))
            noise_g.setColorAt(1, QColor(0, 0, 0, 10))
            p.fillPath(path, QBrush(noise_g))
            hi_path = QPainterPath()
            hi_path.addRoundedRect(
                QRectF(rect.x() + 1, rect.y() + 1,
                       rect.width() - 2, rect.height() * 0.45), r - 1, r - 1)
            p.fillPath(hi_path, QBrush(QColor(255, 255, 255, 18)))

        else:  # solid
            p.fillPath(path, QBrush(_c(s.get("background_color", [15, 15, 25, 235]))))
            # Subtle top sheen even on solid
            sh = QLinearGradient(rect.topLeft(), QPointF(rect.x(), rect.y() + rect.height() * 0.3))
            sh.setColorAt(0, QColor(255, 255, 255, 10))
            sh.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillPath(path, QBrush(sh))

        p.setClipping(False)

        # Border — subtle inner stroke
        bw = s.get("border_width", 1)
        if bw > 0:
            pen = QPen(_c(s.get("border_color", "#ffffff18")))
            pen.setWidthF(bw)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            shrink = bw / 2
            p.drawRoundedRect(
                QRectF(rect.x() + shrink, rect.y() + shrink,
                       rect.width() - bw, rect.height() - bw), r, r)

    # ── Dispatcher ──────────────────────────────────────────────────────────

    def _dispatch(self, p, el, w, h):
        etype = el.get("type", "text")
        rect  = QRectF(el.get("x", 0), el.get("y", 0),
                       el.get("width", w), el.get("height", 30))
        fns = {
            "text":              self._text,
            "clock":             self._clock,
            "analog_clock":      self._analog_clock,
            "date":              self._date,
            "progress":          self._progress,
            "ring":              self._ring,
            "bar_graph":         self._bar_graph,
            "line_graph":        self._line_graph,
            "sparkline":         self._sparkline,
            "system_stat":       self._system_stat,
            "label_value":       self._label_value,
            "weather":           self._weather,
            "weather_forecast":  self._weather_forecast,
            "stock":             self._stock,
            "crypto":            self._crypto,
            "forex":             self._forex,
            "news":              self._news,
            "world_clock":       self._world_clock,
            "battery":           self._battery_el,
            "network":           self._network,
            "divider":           self._divider,
            "image":             self._image,
            "icon":              self._icon,
            "todo_list":         self._todo_list,
            "calendar_mini":     self._calendar_mini,
            "media_now_playing": self._media_now_playing,
            "shortcut_btn":      self._shortcut_btn,
            "countdown":         self._countdown,
            "notification_bar":  self._notification_bar,
            "notes":             self._notes,
            "pomodoro":          self._pomodoro,
            "script_btn":        self._script_btn,
        }
        fn = fns.get(etype)
        if fn:
            fn(p, el, rect)

    # ─── Font helper ────────────────────────────────────────────────────────

    def _font(self, el: dict, size: int = None, weight=None) -> QFont:
        family = el.get("font_family",
                    self.wdef.get("style", {}).get("font_family", "Segoe UI"))
        sz = size if size is not None else el.get("font_size", 13)
        wmap = {
            "thin":   QFont.Thin,   "light":  QFont.Light,
            "normal": QFont.Normal, "medium": QFont.Medium,
            "semibold": QFont.DemiBold,
            "bold":   QFont.Bold,   "black":  QFont.Black,
            "demibold": QFont.DemiBold,
        }
        w_key  = weight if weight else el.get("font_weight", "normal")
        w_val  = wmap.get(w_key, QFont.Normal)
        f = QFont(family, sz)
        f.setWeight(w_val)
        return f

    def _set_font(self, p, el, size=None, weight=None):
        p.setFont(self._font(el, size, weight))

    # ─── TEXT ───────────────────────────────────────────────────────────────

    def _text(self, p, el, rect):
        self._set_font(p, el)
        p.setPen(_c(el.get("color", "#e0e0e0")))
        p.drawText(rect, _align(el.get("align", "left")), el.get("text", ""))

    # ─── CLOCK (Digital) ────────────────────────────────────────────────────

    def _clock(self, p, el, rect):
        # Support both use_12h and time_format keys
        use_12h     = el.get("use_12h", False) or el.get("time_format", "24h") == "12h"
        show_secs   = el.get("show_seconds", False)
        now         = datetime.now()

        # Build format string
        fmt = el.get("format", "")
        if not fmt:
            if use_12h:
                fmt = "%I:%M:%S" if show_secs else "%I:%M"
            else:
                fmt = "%H:%M:%S" if show_secs else "%H:%M"

        # Apply 12h conversion on explicit format strings
        if use_12h:
            fmt = fmt.replace("%H", "%I").replace("%k", "%l")

        text = now.strftime(fmt)
        # Strip leading zero from 12h hour
        if use_12h and text.startswith("0"):
            text = text[1:]

        # If showing seconds, split into main time + seconds with smaller size
        if show_secs and el.get("large_seconds", True):
            # Split HH:MM from :SS for distinct sizes
            parts = text.rsplit(":", 1)
            if len(parts) == 2:
                main_t, secs_t = parts[0], ":" + parts[1]
                # Measure main part width
                main_font = self._font(el)
                fm_main   = QFontMetrics(main_font)
                main_w    = fm_main.horizontalAdvance(main_t)
                total_w   = rect.width()

                # Main time
                p.setFont(main_font)
                p.setPen(_c(el.get("color", "#ffffff")))
                main_r = QRectF(rect.x(), rect.y(), total_w, rect.height())
                p.drawText(main_r, _align(el.get("align", "center")), main_t)

                # Seconds — smaller, muted
                sec_size = max(12, el.get("font_size", 46) // 3)
                sec_font = self._font(el, sec_size, "light")
                p.setFont(sec_font)
                p.setPen(_c(el.get("sec_color", "#666688")))
                fm_main2 = QFontMetrics(main_font)
                offset_x = fm_main2.horizontalAdvance(main_t)
                align    = el.get("align", "center")
                if align == "center":
                    total_txt_w = fm_main2.horizontalAdvance(main_t) + QFontMetrics(sec_font).horizontalAdvance(secs_t)
                    start_x     = rect.x() + (rect.width() - total_txt_w) / 2
                    sec_r = QRectF(start_x + offset_x - (rect.width() - total_txt_w) / 2 + offset_x,
                                   rect.y() + rect.height() * 0.35,
                                   QFontMetrics(sec_font).horizontalAdvance(secs_t) + 10,
                                   rect.height() * 0.5)
                else:
                    sec_r = QRectF(rect.x() + offset_x + 2, rect.y() + rect.height() * 0.38,
                                   rect.width() - offset_x, rect.height() * 0.5)
                p.drawText(sec_r, Qt.AlignLeft | Qt.AlignVCenter, secs_t)
                return

        self._set_font(p, el)
        p.setPen(_c(el.get("color", "#ffffff")))
        p.drawText(rect, _align(el.get("align", "center")), text)

    # ─── ANALOG CLOCK ────────────────────────────────────────────────────────

    def _analog_clock(self, p, el, rect):
        cx, cy = rect.center().x(), rect.center().y()
        r  = min(rect.width(), rect.height()) / 2 - 6
        now = datetime.now()

        # Face with radial gradient (iOS-style depth)
        face_g = QRadialGradient(QPointF(cx, cy - r * 0.2), r * 1.2)
        face_g.setColorAt(0, _c(el.get("face_color", [28, 28, 44, 230])))
        face_g.setColorAt(1, _c(el.get("face_color_edge", [12, 12, 22, 240])))
        face_path = QPainterPath()
        face_path.addEllipse(QPointF(cx, cy), r, r)
        p.fillPath(face_path, QBrush(face_g))

        # Outer ring
        p.setPen(QPen(_c(el.get("border_color", "#ffffff20")), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Inner shimmer ring
        p.setPen(QPen(QColor(255, 255, 255, 8), 1))
        p.drawEllipse(QPointF(cx, cy), r - 2, r - 2)

        # Tick marks (modern minimal style)
        for i in range(60):
            angle = math.radians(i * 6 - 90)
            if i % 15 == 0:
                inner, width, alpha = r * 0.75, 2.0, 200
            elif i % 5 == 0:
                inner, width, alpha = r * 0.83, 1.5, 120
            else:
                inner, width, alpha = r * 0.91, 1.0, 45
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            p.setPen(QPen(QColor(255, 255, 255, alpha), width, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(
                QPointF(cx + cos_a * inner, cy + sin_a * inner),
                QPointF(cx + cos_a * r,     cy + sin_a * r))

        def hand(angle_deg, length, width, color, cap=Qt.RoundCap):
            a = math.radians(angle_deg - 90)
            pen = QPen(_c(color))
            pen.setWidthF(width)
            pen.setCapStyle(cap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            # Tail
            tail = length * 0.18
            p.drawLine(
                QPointF(cx - math.cos(a) * tail, cy - math.sin(a) * tail),
                QPointF(cx + math.cos(a) * length, cy + math.sin(a) * length))

        h_angle = (now.hour % 12 + now.minute / 60) * 30
        m_angle = (now.minute + now.second / 60) * 6
        s_angle = now.second * 6 + now.microsecond / 1_000_000 * 6

        hand(h_angle, r * 0.52, 3.5, el.get("hour_color", "#ffffff"))
        hand(m_angle, r * 0.75, 2.2, el.get("min_color",  "#e0e0f0"))
        hand(s_angle, r * 0.82, 1.2, el.get("sec_color",  "#ff6060"))

        # Center jewel
        p.setBrush(QBrush(_c(el.get("sec_color", "#ff6060"))))
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.drawEllipse(QPointF(cx, cy), 4, 4)
        p.setBrush(QBrush(QColor(255, 255, 255, 200)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx - 1.2, cy - 1.2), 1.5, 1.5)

    # ─── DATE ───────────────────────────────────────────────────────────────

    def _date(self, p, el, rect):
        fmt  = el.get("format", "%A, %B %d")
        text = datetime.now().strftime(fmt)
        self._set_font(p, el)
        p.setPen(_c(el.get("color", "#888888")))
        p.drawText(rect, _align(el.get("align", "center")), text)

    # ─── PROGRESS BAR (iOS style) ───────────────────────────────────────────

    def _progress(self, p, el, rect):
        eid = el.get("id", "")
        raw = self._cache.get(eid, el.get("value", 0))
        val = max(0.0, min(1.0,
              float(raw) / 100.0 if isinstance(raw, (int, float)) and raw > 1
              else float(raw) if raw else 0))
        rr  = el.get("radius", 6)

        # Track
        tp = QPainterPath()
        tp.addRoundedRect(rect, rr, rr)
        p.fillPath(tp, QBrush(_c(el.get("track_color", "#ffffff12"))))

        # Fill with gradient
        if val > 0:
            fr = QRectF(rect.x(), rect.y(), rect.width() * val, rect.height())
            fp = QPainterPath()
            fp.addRoundedRect(fr, rr, rr)
            fc = el.get("fill_color", "#60a5fa")
            if isinstance(fc, list) and len(fc) == 2:
                g = QLinearGradient(fr.topLeft(), fr.topRight())
                g.setColorAt(0, _c(fc[0]))
                g.setColorAt(1, _c(fc[1]))
                p.fillPath(fp, QBrush(g))
            elif el.get("heat", False):
                g = QLinearGradient(fr.topLeft(), fr.topRight())
                g.setColorAt(0, DS.GREEN)
                g.setColorAt(0.6, DS.YELLOW)
                g.setColorAt(1, DS.RED)
                p.fillPath(fp, QBrush(g))
            else:
                p.fillPath(fp, QBrush(_c(fc)))

            # Gloss sheen on top half of fill
            if rect.height() >= 6:
                sh_r = QRectF(fr.x(), fr.y(), fr.width(), fr.height() * 0.5)
                sh_p = QPainterPath()
                sh_p.addRoundedRect(sh_r, rr, rr)
                sh_g = QLinearGradient(sh_r.topLeft(), sh_r.bottomLeft())
                sh_g.setColorAt(0, QColor(255, 255, 255, 30))
                sh_g.setColorAt(1, QColor(255, 255, 255, 0))
                p.fillPath(sh_p, QBrush(sh_g))

        if el.get("show_label", False):
            self._set_font(p, el, 10, "bold")
            p.setPen(QColor("#ffffff"))
            p.drawText(rect, Qt.AlignCenter, f"{int(val * 100)}%")

    # ─── RING GAUGE (iOS-style) ──────────────────────────────────────────────

    def _ring(self, p, el, rect):
        eid = el.get("id", "")
        raw = self._cache.get(eid, el.get("value", 0))
        val = max(0.0, min(1.0,
              float(raw) / 100.0 if isinstance(raw, (int, float)) and float(raw) > 1
              else float(raw) if raw else 0))
        cx, cy = rect.center().x(), rect.center().y()
        thick  = el.get("thickness", 8)
        r      = min(rect.width(), rect.height()) / 2 - thick / 2 - 2

        # Track ring
        pen = QPen(_c(el.get("track_color", "#ffffff10")))
        pen.setWidthF(thick)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Fill arc
        if val > 0:
            fc = el.get("fill_color", "#60a5fa")
            pen2 = QPen(_c(fc))
            pen2.setWidthF(thick)
            pen2.setCapStyle(Qt.RoundCap)
            p.setPen(pen2)
            span = int(-val * 360 * 16)
            p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 90 * 16, span)

        # Center text
        label = el.get("label", "")
        if label or el.get("show_value", True):
            txt = f"{int(val * 100)}%" if el.get("show_value", True) else label
            self._set_font(p, el, el.get("font_size", 14), "semibold")
            p.setPen(_c(el.get("color", "#ffffff")))
            p.drawText(rect, Qt.AlignCenter, txt)

    # ─── BAR GRAPH ──────────────────────────────────────────────────────────

    def _bar_graph(self, p, el, rect):
        eid  = el.get("id", "")
        hist = self._cache.get(eid + "_hist", [0] * 20)
        if not isinstance(hist, list) or not hist:
            hist = [0] * 20
        hist = hist[-el.get("bars", 24):]
        n    = len(hist)
        gap  = el.get("gap", 2)
        bw   = (rect.width() - gap * (n - 1)) / n
        fc_raw = el.get("fill_color", "#60a5fa")

        for i, v in enumerate(hist):
            norm = max(0.0, min(1.0, float(v) / 100 if float(v) > 1 else float(v)))
            bh   = rect.height() * norm
            bx   = rect.x() + i * (bw + gap)
            by   = rect.bottom() - bh
            bp   = QPainterPath()
            bp.addRoundedRect(QRectF(bx, by, bw, bh), 2, 2)
            # Heat colour based on value
            if el.get("heat", False):
                fc = _value_heat(float(v) if float(v) <= 100 else 100)
            else:
                fc = _c(fc_raw + "bb" if isinstance(fc_raw, str) and len(fc_raw) == 7 else fc_raw)
                if i == n - 1:
                    fc = _c(fc_raw)  # Latest bar full opacity
            p.fillPath(bp, QBrush(fc))

    # ─── LINE GRAPH ─────────────────────────────────────────────────────────

    def _line_graph(self, p, el, rect):
        eid  = el.get("id", "")
        hist = self._cache.get(eid + "_hist", [])
        if not isinstance(hist, list) or len(hist) < 2:
            return
        hist = [max(0, min(1, float(v) / 100 if float(v) > 1 else float(v)))
                for v in hist[-60:]]
        n   = len(hist)
        lc  = _c(el.get("line_color", "#60a5fa"))

        # Fill area under line
        path = QPainterPath()
        path.moveTo(rect.x(), rect.bottom())
        for i, v in enumerate(hist):
            x = rect.x() + (i / (n - 1)) * rect.width()
            y = rect.bottom() - v * rect.height()
            if i == 0:
                path.lineTo(x, y)
            else:
                path.lineTo(x, y)
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()

        fill_g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        base_c = _c(el.get("line_color", "#60a5fa"))
        fill_g.setColorAt(0, QColor(base_c.red(), base_c.green(), base_c.blue(), 55))
        fill_g.setColorAt(1, QColor(base_c.red(), base_c.green(), base_c.blue(), 5))
        p.fillPath(path, QBrush(fill_g))

        # Line
        pen = QPen(lc)
        pen.setWidthF(el.get("line_width", 1.8))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        lpath = QPainterPath()
        for i, v in enumerate(hist):
            x = rect.x() + (i / (n - 1)) * rect.width()
            y = rect.bottom() - v * rect.height()
            if i == 0:
                lpath.moveTo(x, y)
            else:
                lpath.lineTo(x, y)
        p.drawPath(lpath)

    # ─── SPARKLINE ──────────────────────────────────────────────────────────

    def _sparkline(self, p, el, rect):
        eid  = el.get("id", "")
        hist = self._cache.get(eid + "_hist", [])
        last = self._cache.get(eid, 0)

        if isinstance(hist, list) and len(hist) >= 2:
            mini_rect = QRectF(rect.x(), rect.y(),
                               rect.width() - 56, rect.height())
            self._line_graph(p, {**el, "id": eid}, mini_rect)

        # Value badge (right side)
        self._set_font(p, el, el.get("font_size", 13), "semibold")
        p.setPen(_c(el.get("color", "#ffffff")))
        val_r = QRectF(rect.right() - 56, rect.y(), 56, rect.height())
        txt = (f"{float(last):.1f}{el.get('unit', '')}"
               if isinstance(last, (int, float)) else str(last))
        p.drawText(val_r, Qt.AlignVCenter | Qt.AlignRight, txt)

    # ─── SYSTEM STAT (text) ──────────────────────────────────────────────────

    def _system_stat(self, p, el, rect):
        eid   = el.get("id", "")
        raw   = self._cache.get(eid, 0)
        try:
            val = float(raw)
        except Exception:
            val = 0.0
        label = el.get("label", "")
        unit  = el.get("unit", "%")
        txt   = f"{label}  {val:.1f}{unit}" if label else f"{val:.1f}{unit}"
        self._set_font(p, el)
        p.setPen(_c(el.get("color", DS.TEXT_PRIMARY.name())))
        p.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, txt)

    # ─── LABEL / VALUE ───────────────────────────────────────────────────────

    def _label_value(self, p, el, rect):
        label  = el.get("label", "")
        eid    = el.get("id", "")
        raw    = self._cache.get(eid, el.get("value", "--"))
        unit   = el.get("unit", "")
        try:
            val_str = f"{float(raw):.1f}{unit}"
        except Exception:
            val_str = str(raw)

        # Label left
        lw = int(rect.width() * 0.45)
        lr = QRectF(rect.x(), rect.y(), lw, rect.height())
        self._set_font(p, el, el.get("label_size", 11))
        p.setPen(_c(el.get("label_color", "#666688")))
        p.drawText(lr, Qt.AlignVCenter | Qt.AlignLeft, label)

        # Value right — larger, brighter
        vr = QRectF(rect.x() + lw, rect.y(), rect.width() - lw, rect.height())
        self._set_font(p, el, el.get("font_size", 13), "semibold")
        p.setPen(_c(el.get("color", "#ffffff")))
        p.drawText(vr, Qt.AlignVCenter | Qt.AlignRight, val_str)

    # ─── WEATHER ────────────────────────────────────────────────────────────

    def _weather(self, p, el, rect):
        eid  = el.get("id", "")
        d    = self._cache.get(eid, {})
        if not isinstance(d, dict):
            d = {}
        icon   = d.get("icon",   "☁")
        temp   = d.get("temp",   "--°")
        desc   = d.get("desc",   "")
        hum    = d.get("humidity", "--")
        wind   = d.get("wind",   "--")
        feels  = d.get("feels",  "--")
        city   = d.get("city",   "")
        uv     = d.get("uv",     "")

        pad = DS.PAD
        # Large icon — left column
        icon_sz = min(int(rect.height()) - pad, 52)
        self._set_font(p, {}, icon_sz - 12)
        p.setPen(Qt.white)
        icon_r = QRectF(rect.x() + pad, rect.y() + 4, icon_sz, rect.height() * 0.55)
        p.drawText(icon_r, Qt.AlignCenter, icon)

        tx    = rect.x() + icon_sz + pad + 8
        avail = rect.right() - tx - pad

        # City name — small, top of text column
        if city:
            self._set_font(p, el, 10, "semibold")
            p.setPen(DS.TEXT_SECONDARY)
            p.drawText(QRectF(tx, rect.y() + 5, avail, 15),
                       Qt.AlignVCenter | Qt.AlignLeft, city.upper())

        # Temperature — large, main reading
        temp_y_off = 18 if city else 4
        self._set_font(p, el, el.get("temp_size", 28), "light")
        p.setPen(_c(el.get("color", "#ffffff")))
        p.drawText(QRectF(tx, rect.y() + temp_y_off, avail, rect.height() * 0.45),
                   Qt.AlignVCenter | Qt.AlignLeft, temp)

        # Description line
        desc_y = rect.y() + temp_y_off + rect.height() * 0.45
        self._set_font(p, el, 11)
        p.setPen(DS.TEXT_SECONDARY)
        desc_text = desc.capitalize()
        if uv:
            desc_text += f"  ·  {uv}"
        p.drawText(QRectF(tx, desc_y, avail, 16),
                   Qt.AlignVCenter | Qt.AlignLeft, desc_text)

        # Details chips at bottom
        if el.get("show_details", True) and rect.height() > 72:
            chips = [f"💧 {hum}", f"💨 {wind}", f"🌡 {feels}"]
            cw = rect.width() / len(chips)
            for i, chip in enumerate(chips):
                cr = QRectF(rect.x() + i * cw, rect.bottom() - 22, cw, 20)
                pp2 = QPainterPath()
                pp2.addRoundedRect(cr.adjusted(2, 0, -2, 0), 8, 8)
                p.fillPath(pp2, QBrush(QColor(255, 255, 255, 10)))
                self._set_font(p, el, 10)
                p.setPen(DS.TEXT_TERTIARY)
                p.drawText(cr, Qt.AlignCenter, chip)

    # ─── WEATHER FORECAST ────────────────────────────────────────────────────

    def _weather_forecast(self, p, el, rect):
        # ── Try to use live forecast data from weather cache ──────────────
        # weather_forecast shares the same data_provider as the weather element
        # (both use provider_args pointing to the same lat/lon).
        # We look for a sibling weather element's cached data in _cache.
        live_forecast = None
        for eid_key, val in self._cache.items():
            if isinstance(val, dict) and "forecast" in val and val["forecast"]:
                live_forecast = val["forecast"]
                break

        static_fallback = [
            {"time": "Now", "icon": "☀",  "temp": "--°"},
            {"time": "+1h", "icon": "⛅", "temp": "--°"},
            {"time": "+2h", "icon": "☁",  "temp": "--°"},
            {"time": "+3h", "icon": "🌧",  "temp": "--°"},
            {"time": "+4h", "icon": "🌙", "temp": "--°"},
        ]
        slots = live_forecast if live_forecast else el.get("slots", static_fallback)
        n  = len(slots)
        if n == 0:
            return
        sw = rect.width() / n

        for i, slot in enumerate(slots):
            sr = QRectF(rect.x() + i * sw, rect.y(), sw, rect.height())

            # Active column highlight for "Now"
            if i == 0:
                hi_p = QPainterPath()
                hi_p.addRoundedRect(sr.adjusted(2, 2, -2, -2), 8, 8)
                p.fillPath(hi_p, QBrush(QColor(255, 255, 255, 8)))

            # Vertical separator (except last)
            if i < n - 1:
                p.setPen(QPen(QColor(255, 255, 255, 12), 1))
                x_sep = sr.right()
                p.drawLine(QPointF(x_sep, sr.y() + 6), QPointF(x_sep, sr.bottom() - 6))

            # Time label
            self._set_font(p, el, 9, "semibold")
            p.setPen(DS.TEXT_ACCENT if i == 0 else DS.TEXT_TERTIARY)
            p.drawText(QRectF(sr.x(), sr.y() + 4, sr.width(), 14),
                       Qt.AlignCenter, slot.get("time", ""))

            # Weather icon (emoji)
            self._set_font(p, {}, 18)
            p.setPen(Qt.white)
            p.drawText(QRectF(sr.x(), sr.y() + 16, sr.width(), 26),
                       Qt.AlignCenter, slot.get("icon", "?"))

            # Temperature
            self._set_font(p, el, 12, "medium")
            p.setPen(_c(el.get("color", "#e0e0e0")))
            p.drawText(QRectF(sr.x(), sr.y() + 42, sr.width(), 18),
                       Qt.AlignCenter, slot.get("temp", "--"))

    # ─── STOCK ──────────────────────────────────────────────────────────────

    def _stock(self, p, el, rect):
        eid    = el.get("id", "")
        d      = self._cache.get(eid, {})
        if not isinstance(d, dict):
            d = {}
        sym    = d.get("symbol", el.get("provider_args", {}).get("symbol", "AAPL"))
        price  = d.get("price", 0)
        change = d.get("change", 0)
        pct    = d.get("pct", 0)
        up     = d.get("up", True)
        arrow  = "▲" if up else "▼"
        accent = DS.GREEN if up else DS.RED

        # Symbol
        self._set_font(p, el, el.get("font_size", 16), "semibold")
        p.setPen(DS.TEXT_PRIMARY)
        p.drawText(QRectF(rect.x(), rect.y(), rect.width() * 0.45, rect.height() * 0.6),
                   Qt.AlignVCenter | Qt.AlignLeft, sym)

        # Price
        self._set_font(p, el, el.get("font_size", 16), "light")
        p.setPen(DS.TEXT_PRIMARY)
        p.drawText(QRectF(rect.x(), rect.y(), rect.width(), rect.height() * 0.6),
                   Qt.AlignVCenter | Qt.AlignRight, f"${price:,.2f}")

        # Change badge
        if rect.height() > 35:
            badge_txt = f"{arrow} {pct:+.2f}%"
            badge_r   = QRectF(rect.right() - 90, rect.bottom() - 18, 90, 16)
            bb        = QPainterPath()
            bb.addRoundedRect(badge_r, 6, 6)
            p.fillPath(bb, QBrush(QColor(accent.red(), accent.green(), accent.blue(), 28)))
            self._set_font(p, el, 10, "semibold")
            p.setPen(accent)
            p.drawText(badge_r, Qt.AlignCenter, badge_txt)

            # Change value
            self._set_font(p, el, 10)
            p.setPen(DS.TEXT_TERTIARY)
            p.drawText(QRectF(rect.x(), rect.bottom() - 18, rect.width() - 96, 16),
                       Qt.AlignVCenter | Qt.AlignLeft,
                       f"{change:+.2f}")

    # ─── CRYPTO ─────────────────────────────────────────────────────────────

    def _crypto(self, p, el, rect):
        eid    = el.get("id", "")
        d      = self._cache.get(eid, {})
        if not isinstance(d, dict):
            d = {}
        coin   = d.get("coin",   "Bitcoin")
        price  = d.get("price",  0)
        change = d.get("change", 0)
        vs     = d.get("vs",     "USD")
        up     = d.get("up",     True)
        arrow  = "▲" if up else "▼"
        accent = DS.GREEN if up else DS.RED

        self._set_font(p, el, el.get("font_size", 14), "semibold")
        p.setPen(DS.TEXT_PRIMARY)
        p.drawText(QRectF(rect.x(), rect.y(), rect.width() * 0.5, rect.height() * 0.6),
                   Qt.AlignVCenter | Qt.AlignLeft, coin)

        price_str = f"${price:,.2f}" if vs == "USD" else f"{price:,.2f} {vs}"
        self._set_font(p, el, el.get("font_size", 14), "light")
        p.drawText(QRectF(rect.x(), rect.y(), rect.width(), rect.height() * 0.6),
                   Qt.AlignVCenter | Qt.AlignRight, price_str)

        # Pct change pill
        self._set_font(p, el, 10, "semibold")
        p.setPen(accent)
        p.drawText(QRectF(rect.x(), rect.y() + rect.height() * 0.6,
                          rect.width(), rect.height() * 0.4),
                   Qt.AlignVCenter | Qt.AlignRight, f"{arrow} {change:+.2f}% 24h")

    # ─── FOREX ──────────────────────────────────────────────────────────────

    def _forex(self, p, el, rect):
        eid    = el.get("id", "")
        d      = self._cache.get(eid, {})
        if not isinstance(d, dict):
            d = {}
        base   = d.get("base",   "USD")
        target = d.get("target", "EUR")
        rate   = d.get("rate",   0)

        self._set_font(p, el, el.get("font_size", 12))
        p.setPen(DS.TEXT_SECONDARY)
        p.drawText(QRectF(rect.x(), rect.y(), rect.width() * 0.5, rect.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, f"{base} / {target}")

        self._set_font(p, el, el.get("font_size", 14), "semibold")
        p.setPen(DS.TEXT_PRIMARY)
        p.drawText(QRectF(rect.x(), rect.y(), rect.width(), rect.height()),
                   Qt.AlignVCenter | Qt.AlignRight, f"{rate:.4f}")

    # ─── NEWS ───────────────────────────────────────────────────────────────

    def _news(self, p, el, rect):
        eid    = el.get("id", "")
        d      = self._cache.get(eid, {})
        if not isinstance(d, dict):
            d = {}
        items  = d.get("items", [{"title": "Loading news…", "desc": "", "pub": ""}])
        source = d.get("source", "")
        pad    = 12

        # ── Source header bar ────────────────────────────────────────────
        hdr_h = 22
        hdr_r = QRectF(rect.x(), rect.y(), rect.width(), hdr_h)
        hdr_p = QPainterPath()
        hdr_p.addRoundedRect(hdr_r, 8, 8)
        accent = _c(el.get("accent", "#3b82f6"))
        p.fillPath(hdr_p, QBrush(QColor(accent.red(), accent.green(), accent.blue(), 30)))

        self._set_font(p, el, 9, "bold")
        p.setPen(QColor(accent.red(), accent.green(), accent.blue(), 200))
        src_label = f"📰  {source.upper()}" if source else "📰  NEWS"
        p.drawText(QRectF(rect.x() + pad, rect.y(), rect.width() - pad, hdr_h),
                   Qt.AlignVCenter | Qt.AlignLeft, src_label)

        # ── News items — full wrapping text ──────────────────────────────
        font_title = self._font(el, el.get("font_size", 12), "semibold")
        font_desc  = self._font(el, max(9, el.get("font_size", 12) - 2), "normal")
        font_pub   = self._font(el, 9, "normal")

        fm_title = QFontMetrics(font_title)
        fm_desc  = QFontMetrics(font_desc)

        line_h_title = fm_title.height()
        line_h_desc  = fm_desc.height()
        text_w       = rect.width() - pad * 2 - 8   # 8 = dot + gap

        y = rect.y() + hdr_h + 6

        show_desc = el.get("show_description", True)

        for i, item in enumerate(items):
            if y >= rect.bottom() - 4:
                break

            title = item.get("title", "")
            desc  = item.get("desc",  "")
            pub   = item.get("pub",   "")

            # ── Item card background (alternating) ───────────────────────
            # Measure how tall this item will be before drawing
            title_lines = fm_title.boundingRect(
                0, 0, int(text_w), 9999,
                Qt.TextWordWrap | Qt.AlignLeft, title
            ).height() // line_h_title + 1
            title_block_h = title_lines * line_h_title

            desc_block_h = 0
            if show_desc and desc:
                desc_lines = fm_desc.boundingRect(
                    0, 0, int(text_w), 9999,
                    Qt.TextWordWrap | Qt.AlignLeft, desc
                ).height() // line_h_desc + 1
                desc_lines  = min(desc_lines, el.get("desc_max_lines", 3))
                desc_block_h = desc_lines * line_h_desc + 2

            pub_h    = 14 if pub else 0
            item_h   = title_block_h + desc_block_h + pub_h + 10
            item_h   = max(item_h, 28)

            # Clip: don't draw past bottom
            if y + item_h > rect.bottom():
                item_h = rect.bottom() - y
                if item_h < 16:
                    break

            # Card tint on alternating rows
            if i % 2 == 0:
                card_p = QPainterPath()
                card_p.addRoundedRect(
                    QRectF(rect.x() + 2, y + 1, rect.width() - 4, item_h - 2), 7, 7)
                p.fillPath(card_p, QBrush(QColor(255, 255, 255, 5)))

            # Accent bar on left edge
            bar_p = QPainterPath()
            bar_p.addRoundedRect(QRectF(rect.x() + 3, y + 4, 3, item_h - 8), 2, 2)
            bar_col = QColor(accent.red(), accent.green(), accent.blue(),
                             180 if i == 0 else 80)
            p.fillPath(bar_p, QBrush(bar_col))

            cx = rect.x() + pad + 4   # left edge of text (after bar)
            cy = y + 5

            # ── Title (word-wrapped, full) ────────────────────────────────
            p.setFont(font_title)
            p.setPen(DS.TEXT_PRIMARY)
            title_rect = QRectF(cx, cy, text_w, title_block_h + 2)
            p.drawText(title_rect,
                       Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, title)
            cy += title_block_h + 2

            # ── Description (word-wrapped, muted, capped lines) ──────────
            if show_desc and desc and cy < y + item_h - 4:
                p.setFont(font_desc)
                p.setPen(DS.TEXT_SECONDARY)
                avail_desc_h = max(line_h_desc, y + item_h - cy - pub_h - 4)
                p.drawText(
                    QRectF(cx, cy, text_w, avail_desc_h),
                    Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, desc)
                cy += avail_desc_h + 2

            # ── Publication time ─────────────────────────────────────────
            if pub and cy < y + item_h:
                p.setFont(font_pub)
                p.setPen(DS.TEXT_TERTIARY)
                p.drawText(QRectF(cx, cy, text_w, 14),
                           Qt.AlignVCenter | Qt.AlignLeft, pub)

            # Separator
            sep_y = y + item_h - 1
            if i < len(items) - 1:
                sep_g = QLinearGradient(
                    QPointF(rect.x() + 20, sep_y),
                    QPointF(rect.right() - 20, sep_y))
                sep_g.setColorAt(0, QColor(255, 255, 255, 0))
                sep_g.setColorAt(0.3, QColor(255, 255, 255, 14))
                sep_g.setColorAt(0.7, QColor(255, 255, 255, 14))
                sep_g.setColorAt(1, QColor(255, 255, 255, 0))
                p.setPen(QPen(QBrush(sep_g), 1))
                p.drawLine(QPointF(rect.x() + 20, sep_y),
                           QPointF(rect.right() - 20, sep_y))

            y += item_h

    # ─── WORLD CLOCK ────────────────────────────────────────────────────────

    def _world_clock(self, p, el, rect):
        eid = el.get("id", "")
        d   = self._cache.get(eid, {})
        if not isinstance(d, dict):
            d = {}
        clocks = d.get("clocks", [{"label": "UTC", "time": "--:--", "date": ""}])
        n  = len(clocks)
        rh = rect.height() / n

        for i, c in enumerate(clocks):
            cr = QRectF(rect.x(), rect.y() + i * rh, rect.width(), rh)

            # Row separator
            if i > 0:
                p.setPen(QPen(QColor(255, 255, 255, 10), 1))
                p.drawLine(QPointF(cr.x() + 8, cr.y()), QPointF(cr.right() - 8, cr.y()))

            # City label
            self._set_font(p, el, 10)
            p.setPen(DS.TEXT_SECONDARY)
            p.drawText(QRectF(cr.x(), cr.y(), cr.width() * 0.48, cr.height()),
                       Qt.AlignVCenter | Qt.AlignLeft, c.get("label", ""))

            # Time
            self._set_font(p, el, el.get("font_size", 16), "light")
            p.setPen(DS.TEXT_PRIMARY)
            p.drawText(QRectF(cr.x(), cr.y(), cr.width(), cr.height()),
                       Qt.AlignVCenter | Qt.AlignRight, c.get("time", "--:--"))

    # ─── BATTERY ────────────────────────────────────────────────────────────

    def _battery_el(self, p, el, rect):
        eid     = el.get("id", "")
        d       = self._cache.get(eid, {})
        if not isinstance(d, dict):
            d = {}
        pct     = d.get("percent", 100)
        plugged = d.get("plugged", True)
        rem     = d.get("remaining", "")

        if plugged:
            fill_c = DS.BLUE
        elif pct > 30:
            fill_c = DS.GREEN
        elif pct > 15:
            fill_c = DS.YELLOW
        else:
            fill_c = DS.RED

        pad = DS.PAD
        bw  = min(140, rect.width() - pad * 2 - 60)
        bh  = 20
        bx  = rect.x() + pad
        by  = rect.y() + (rect.height() - bh) / 2

        # Battery body
        body = QRectF(bx, by, bw, bh)
        bp   = QPainterPath()
        bp.addRoundedRect(body, 4, 4)
        p.fillPath(bp, QBrush(QColor(255, 255, 255, 15)))

        # Terminal nub
        nw, nh = 4, 8
        nub = QRectF(bx + bw, by + (bh - nh) / 2, nw, nh)
        np2 = QPainterPath()
        np2.addRoundedRect(nub, 2, 2)
        p.fillPath(np2, QBrush(QColor(255, 255, 255, 30)))

        # Fill
        fill_w = max(0.0, (bw - 4) * pct / 100)
        if fill_w > 0:
            fp = QPainterPath()
            fp.addRoundedRect(QRectF(bx + 2, by + 2, fill_w, bh - 4), 3, 3)
            p.fillPath(fp, QBrush(fill_c))
            # Gloss
            gp = QPainterPath()
            gp.addRoundedRect(QRectF(bx + 2, by + 2, fill_w, (bh - 4) * 0.45), 3, 3)
            p.fillPath(gp, QBrush(QColor(255, 255, 255, 30)))

        # Border
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(body, 4, 4)

        # Text
        icon = "⚡" if plugged else f"{int(pct)}%"
        self._set_font(p, el, 11)
        p.setPen(DS.TEXT_SECONDARY)
        p.drawText(QRectF(bx + bw + 10, by, 80, bh),
                   Qt.AlignVCenter | Qt.AlignLeft, f"{icon}  {rem}")

    # ─── NETWORK ────────────────────────────────────────────────────────────

    def _network(self, p, el, rect):
        eid = el.get("id", "")
        d   = self._cache.get(eid, {})
        if not isinstance(d, dict):
            d = {}
        dl = d.get("download", 0)
        ul = d.get("upload",   0)

        # Down arrow pill
        half = rect.width() / 2
        self._set_font(p, el, 12, "medium")
        p.setPen(DS.CYAN)
        p.drawText(QRectF(rect.x(), rect.y(), half - 4, rect.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, f"↓  {_fmt_bytes(dl)}")
        p.setPen(DS.PURPLE)
        p.drawText(QRectF(rect.x() + half + 4, rect.y(), half - 4, rect.height()),
                   Qt.AlignVCenter | Qt.AlignRight, f"↑  {_fmt_bytes(ul)}")

    # ─── DIVIDER ────────────────────────────────────────────────────────────

    def _divider(self, p, el, rect):
        # Gradient fade-in-out divider
        g = QLinearGradient(rect.topLeft(), rect.topRight())
        base = _c(el.get("color", "#ffffff10"))
        g.setColorAt(0,   QColor(base.red(), base.green(), base.blue(), 0))
        g.setColorAt(0.2, base)
        g.setColorAt(0.8, base)
        g.setColorAt(1,   QColor(base.red(), base.green(), base.blue(), 0))
        pen = QPen(QBrush(g), el.get("thickness", 1.0))
        p.setPen(pen)
        y = rect.center().y()
        p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

    # ─── IMAGE ──────────────────────────────────────────────────────────────

    def _image(self, p, el, rect):
        path = el.get("path", "")
        if not path:
            return
        pix = QPixmap(path)
        if pix.isNull():
            return
        r = el.get("border_radius", 8)
        if r > 0:
            clip = QPainterPath()
            clip.addRoundedRect(rect, r, r)
            p.setClipPath(clip)
        p.drawPixmap(rect.toRect(),
                     pix.scaled(int(rect.width()), int(rect.height()),
                                Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if r > 0:
            p.setClipping(False)

    # ─── ICON ───────────────────────────────────────────────────────────────

    def _icon(self, p, el, rect):
        # Subtle glow circle behind icon
        gc = QPainterPath()
        gc.addEllipse(rect.center(), rect.width() * 0.38, rect.height() * 0.38)
        ic = _c(el.get("glow_color", "#60a5fa"))
        p.fillPath(gc, QBrush(QColor(ic.red(), ic.green(), ic.blue(), 18)))

        self._set_font(p, el, el.get("font_size", 20))
        p.setPen(_c(el.get("color", "#ffffff")))
        p.drawText(rect, Qt.AlignCenter, el.get("char", "●"))

    # ─── TODO LIST ──────────────────────────────────────────────────────────

    def _todo_list(self, p, el, rect):
        items = el.get("items", [])
        row_h = el.get("row_height", 26)
        y     = rect.y()

        for i, item in enumerate(items):
            if y + row_h > rect.bottom():
                break
            done = item.get("done", False)
            ir   = QRectF(rect.x(), y, rect.width(), row_h)

            # Row hover bg (alternating subtle tint)
            if not done and i % 2 == 0:
                rp = QPainterPath()
                rp.addRoundedRect(ir.adjusted(0, 1, 0, -1), 6, 6)
                p.fillPath(rp, QBrush(QColor(255, 255, 255, 4)))

            # Checkbox
            box_r = QRectF(ir.x() + 2, ir.center().y() - 7, 14, 14)
            bp2   = QPainterPath()
            bp2.addRoundedRect(box_r, 4, 4)
            if done:
                p.fillPath(bp2, QBrush(DS.GREEN))
                self._set_font(p, el, 9, "bold")
                p.setPen(QColor("#000000"))
                p.drawText(box_r, Qt.AlignCenter, "✓")
            else:
                p.fillPath(bp2, QBrush(QColor(255, 255, 255, 12)))
                p.setPen(QPen(QColor(255, 255, 255, 30), 1))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(box_r, 4, 4)

            # Text
            self._set_font(p, el, el.get("font_size", 12))
            p.setPen(DS.TEXT_TERTIARY if done else DS.TEXT_PRIMARY)
            txt_r = QRectF(ir.x() + 22, ir.y(), ir.width() - 24, ir.height())
            fm    = QFontMetrics(p.font())
            txt   = item.get("text", "")
            if done:
                # Strikethrough simulation
                bw = fm.horizontalAdvance(txt)
                p.drawText(txt_r, Qt.AlignVCenter | Qt.AlignLeft, txt)
                y_st = txt_r.center().y()
                p.setPen(QPen(DS.TEXT_TERTIARY, 1))
                p.drawLine(QPointF(txt_r.x(), y_st),
                           QPointF(txt_r.x() + min(bw, txt_r.width()), y_st))
            else:
                p.drawText(txt_r, Qt.AlignVCenter | Qt.AlignLeft, txt)
            y += row_h

    # ─── CALENDAR MINI ──────────────────────────────────────────────────────

    def _calendar_mini(self, p, el, rect):
        import calendar as cal_mod
        now = datetime.now()
        month_days = cal_mod.monthcalendar(now.year, now.month)

        # Header
        header = now.strftime("%B %Y")
        self._set_font(p, el, 12, "semibold")
        p.setPen(DS.TEXT_PRIMARY)
        p.drawText(QRectF(rect.x(), rect.y(), rect.width(), 22), Qt.AlignCenter, header)

        # Day headers
        days = ["M", "T", "W", "T", "F", "S", "S"]
        day_colors = [DS.TEXT_SECONDARY] * 5 + [DS.RED, DS.TEXT_TERTIARY]
        cw = rect.width() / 7
        for i, (d, dc) in enumerate(zip(days, day_colors)):
            self._set_font(p, el, 9, "bold")
            p.setPen(dc)
            p.drawText(QRectF(rect.x() + i * cw, rect.y() + 22, cw, 16), Qt.AlignCenter, d)

        # Days
        row_h = min(20, (rect.height() - 40) / max(len(month_days), 1))
        for wi, week in enumerate(month_days):
            for di, day in enumerate(week):
                if day == 0:
                    continue
                dr     = QRectF(rect.x() + di * cw, rect.y() + 40 + wi * row_h, cw, row_h)
                is_today = day == now.day
                is_weekend = di >= 5

                if is_today:
                    # Today pill
                    tp = QPainterPath()
                    cr = min(dr.width(), dr.height()) * 0.42
                    tp.addEllipse(dr.center(), cr, cr)
                    tc = _c(el.get("today_color", "#3b82f6"))
                    p.fillPath(tp, QBrush(tc))
                    self._set_font(p, el, 10, "bold")
                    p.setPen(QColor("#ffffff"))
                else:
                    self._set_font(p, el, 10)
                    p.setPen(DS.RED if is_weekend else DS.TEXT_PRIMARY)
                p.drawText(dr, Qt.AlignCenter, str(day))

    # ═══════════════════════════════════════════════════════════════════════
    # NEW 2026 ELEMENT RENDERERS
    # ═══════════════════════════════════════════════════════════════════════

    def _media_now_playing(self, p, el, rect):
        """
        Full media now-playing card — embedded in any canvas.
        Reads state from widgets.media.media_controller.
        """
        try:
            from widgets.media import media_controller as MC
            state = MC.get_state()
        except Exception:
            state = {}

        playing  = state.get("playing",  False)
        title    = state.get("title",    "No Media Playing")
        artist   = state.get("artist",   "")
        prog     = max(0.0, min(1.0, state.get("progress", 0.0)))
        source   = state.get("source",   "")
        art_data = state.get("art_data")
        art_url  = state.get("art_url",  "")
        pos_s    = state.get("position_s", 0)
        dur_s    = state.get("duration_s", 0)

        SOURCE_ACCENT = {
            "spotify": "#1DB954",
            "vlc":     "#FF8800",
            "chrome":  "#4285F4",
            "edge":    "#0078D4",
            "wmp":     "#00ADEF",
            "movies":  "#7B68EE",
            "":        "#60a5fa",
        }
        accent = _c(SOURCE_ACCENT.get(source, "#60a5fa"))

        # ── Background ──────────────────────────────────────────────────
        bg_p = QPainterPath()
        bg_p.addRoundedRect(rect, el.get("border_radius", DS.R_CARD), el.get("border_radius", DS.R_CARD))
        bg_g = QLinearGradient(rect.topLeft(), rect.bottomRight())
        bg_g.setColorAt(0, QColor(16, 16, 26, 230))
        bg_g.setColorAt(1, QColor(8,   8, 18, 235))
        p.fillPath(bg_p, QBrush(bg_g))

        # Accent stripe at top
        stripe_p = QPainterPath()
        stripe_p.addRoundedRect(QRectF(rect.x(), rect.y(), rect.width(), 3),
                                DS.R_CARD, DS.R_CARD)
        p.fillPath(stripe_p, QBrush(QColor(accent.red(), accent.green(), accent.blue(), 160)))

        # ── Album art ───────────────────────────────────────────────────
        art_size = min(int(rect.height()) - 24, 86)
        ax  = rect.x() + 12
        ay  = rect.y() + (rect.height() - art_size) / 2
        art_rect = QRectF(ax, ay, art_size, art_size)

        if el.get("show_art", True):
            pix = None
            if art_data:
                key = art_url or str(id(art_data))
                if key not in self._art_cache:
                    img = QImage()
                    img.loadFromData(art_data)
                    self._art_cache[key] = QPixmap.fromImage(img)
                pix = self._art_cache.get(key)

            art_clip = QPainterPath()
            art_clip.addRoundedRect(art_rect, DS.R_INNER, DS.R_INNER)

            # Shadow
            sh_p = QPainterPath()
            sh_p.addRoundedRect(art_rect.adjusted(3, 3, 3, 3), DS.R_INNER, DS.R_INNER)
            p.fillPath(sh_p, QColor(0, 0, 0, 70))

            p.setClipPath(art_clip)
            if pix and not pix.isNull():
                p.drawPixmap(art_rect.toRect(),
                             pix.scaled(art_size, art_size,
                                        Qt.KeepAspectRatioByExpanding,
                                        Qt.SmoothTransformation))
            else:
                p.fillPath(art_clip, QBrush(QColor(28, 28, 46)))
                self._set_font(p, el, 26)
                p.setPen(QColor(60, 60, 90))
                p.drawText(art_rect, Qt.AlignCenter, "♫")
            p.setClipping(False)
            text_x = ax + art_size + 14
        else:
            text_x = rect.x() + 14

        avail_w = rect.right() - text_x - 12

        # ── Source badge ─────────────────────────────────────────────────
        src_name = source.upper() if source else "MEDIA"
        self._set_font(p, el, 9, "bold")
        p.setPen(QColor(accent.red(), accent.green(), accent.blue(), 190))
        p.drawText(QRectF(text_x, rect.y() + 9, avail_w, 13),
                   Qt.AlignVCenter | Qt.AlignLeft, f"♫  {src_name}")

        # ── Title ────────────────────────────────────────────────────────
        self._set_font(p, el, el.get("font_size", 13), "semibold")
        p.setPen(DS.TEXT_PRIMARY)
        fm = QFontMetrics(p.font())
        p.drawText(QRectF(text_x, rect.y() + 23, avail_w, 20),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   fm.elidedText(title, Qt.ElideRight, int(avail_w)))

        # ── Artist ────────────────────────────────────────────────────────
        self._set_font(p, el, 11)
        p.setPen(DS.TEXT_SECONDARY)
        fm2 = QFontMetrics(p.font())
        p.drawText(QRectF(text_x, rect.y() + 44, avail_w, 17),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   fm2.elidedText(artist, Qt.ElideRight, int(avail_w)))

        # ── Progress bar ─────────────────────────────────────────────────
        bar_m = 14
        bar_y  = rect.bottom() - 38
        bar_x  = rect.x() + bar_m
        bar_w  = rect.width() - bar_m * 2
        bar_h  = 3.5

        trk = QPainterPath()
        trk.addRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)
        p.fillPath(trk, QBrush(QColor(255, 255, 255, 20)))

        if prog > 0:
            fp = QPainterPath()
            fp.addRoundedRect(QRectF(bar_x, bar_y, bar_w * prog, bar_h), 2, 2)
            p.fillPath(fp, QBrush(accent))
            # Scrubber dot
            p.setBrush(QBrush(accent.lighter(120)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(bar_x + bar_w * prog, bar_y + bar_h / 2), 5, 5)

        # Time labels
        def _fmt_t(s):
            return f"{s // 60}:{s % 60:02d}"

        self._set_font(p, el, 9)
        p.setPen(DS.TEXT_TERTIARY)
        p.drawText(QRectF(bar_x, bar_y + 6, 44, 14),
                   Qt.AlignVCenter | Qt.AlignLeft, _fmt_t(pos_s))
        p.drawText(QRectF(bar_x, bar_y + 6, bar_w, 14),
                   Qt.AlignVCenter | Qt.AlignRight, _fmt_t(dur_s))

        # ── Controls ─────────────────────────────────────────────────────
        if el.get("show_controls", True):
            cy2  = int(rect.bottom() - 14)
            cx2  = int(rect.x() + rect.width() / 2)
            BTNS = [
                ("prev", cx2 - 38, "⏮"),
                ("play", cx2,      "⏸" if playing else "▶"),
                ("next", cx2 + 38, "⏭"),
            ]
            for key, bx2, icon in BTNS:
                if key == "play":
                    p.setBrush(QBrush(accent))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(QPointF(bx2, cy2), 14, 14)
                    self._set_font(p, el, 12, "bold")
                    p.setPen(QColor("#000000"))
                else:
                    self._set_font(p, el, 15)
                    p.setPen(DS.TEXT_SECONDARY)
                p.drawText(QRectF(bx2 - 14, cy2 - 13, 28, 26), Qt.AlignCenter, icon)

    def _shortcut_btn(self, p, el, rect):
        """Modern iOS-style shortcut launcher button."""
        icon   = el.get("icon",  "▶")
        label  = el.get("label", "App")
        color  = _c(el.get("color", "#3b82f6"))
        radius = el.get("radius", DS.R_INNER)

        # Glassmorphic background
        bg = QPainterPath()
        bg.addRoundedRect(rect, radius, radius)
        bg_g = QLinearGradient(rect.topLeft(), rect.bottomRight())
        bg_g.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 35))
        bg_g.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 20))
        p.fillPath(bg, QBrush(bg_g))

        # Border
        bp = QPen(QColor(color.red(), color.green(), color.blue(), 70))
        bp.setWidthF(1)
        p.setPen(bp)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

        # Icon
        self._set_font(p, {}, min(22, int(rect.height() * 0.38)))
        p.setPen(_c(el.get("icon_color", "#ffffff")))
        p.drawText(QRectF(rect.x(), rect.y() + 2,
                          rect.width(), rect.height() * 0.58), Qt.AlignCenter, icon)

        # Label
        self._set_font(p, el, el.get("font_size", 10))
        p.setPen(DS.TEXT_SECONDARY)
        p.drawText(QRectF(rect.x(), rect.y() + rect.height() * 0.58,
                          rect.width(), rect.height() * 0.42), Qt.AlignCenter, label)

    def _countdown(self, p, el, rect):
        """iOS-style countdown with large number and subtle label."""
        import datetime as dt
        target_str = el.get("target_date", "")
        label      = el.get("label", "Countdown")

        try:
            target = dt.datetime.strptime(target_str, "%Y-%m-%d")
            now    = dt.datetime.now()
            delta  = target - now
            days   = max(0, delta.days)
            hrs    = max(0, delta.seconds // 3600) if delta.total_seconds() > 0 else 0
        except Exception:
            days, hrs = 0, 0

        # Label (top pill)
        self._set_font(p, el, 9, "bold")
        p.setPen(DS.TEXT_TERTIARY)
        p.drawText(QRectF(rect.x(), rect.y() + 8, rect.width(), 16),
                   Qt.AlignCenter, label.upper())

        # Big number
        self._set_font(p, el, el.get("font_size", 44), el.get("font_weight", "thin"))
        p.setPen(_c(el.get("color", "#ffffff")))
        p.drawText(QRectF(rect.x(), rect.y() + 16, rect.width(), rect.height() * 0.58),
                   Qt.AlignCenter, str(days))

        # Sub-label
        self._set_font(p, el, 10)
        p.setPen(DS.TEXT_TERTIARY)
        p.drawText(QRectF(rect.x(), rect.bottom() - 22, rect.width(), 20),
                   Qt.AlignCenter, f"days  ·  {hrs}h left")

    def _notification_bar(self, p, el, rect):
        """Status / notification pill bar."""
        items  = el.get("items", ["Notification"])
        idx    = el.get("_scroll_idx", 0)
        text   = items[idx % len(items)] if items else ""
        accent = _c(el.get("accent", "#3b82f6"))

        # Frosted pill
        bg = QPainterPath()
        bg.addRoundedRect(rect, DS.R_PILL, DS.R_PILL)
        p.fillPath(bg, QBrush(QColor(255, 255, 255, 10)))

        # Coloured dot
        p.setBrush(QBrush(accent))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(rect.x() + 12, rect.center().y()), 3.5, 3.5)

        # Text
        self._set_font(p, el, el.get("font_size", 11))
        p.setPen(DS.TEXT_SECONDARY)
        p.drawText(QRectF(rect.x() + 22, rect.y(), rect.width() - 26, rect.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, text)

    # ─── NOTES WIDGET ────────────────────────────────────────────────────────

    def _notes(self, p, el, rect):
        """Simple sticky-note widget."""
        text  = el.get("text", "Tap to add notes…")
        lines = text.split("\n")

        # Warm background tint
        note_c = _c(el.get("note_color", "#fefce8"))
        bg = QPainterPath()
        bg.addRoundedRect(rect, DS.R_INNER, DS.R_INNER)
        p.fillPath(bg, QBrush(QColor(note_c.red(), note_c.green(), note_c.blue(), 22)))

        # Fold corner
        fold = 14
        fold_path = QPainterPath()
        fold_path.moveTo(rect.right() - fold, rect.y())
        fold_path.lineTo(rect.right(), rect.y() + fold)
        fold_path.lineTo(rect.right() - fold, rect.y() + fold)
        fold_path.closeSubpath()
        p.fillPath(fold_path, QBrush(QColor(255, 255, 255, 25)))

        # Title line
        title = el.get("title", "")
        if title:
            self._set_font(p, el, el.get("title_size", 11), "semibold")
            p.setPen(_c(el.get("title_color", "#fde68a")))
            p.drawText(QRectF(rect.x() + 12, rect.y() + 10,
                              rect.width() - 24, 18),
                       Qt.AlignVCenter | Qt.AlignLeft, title)
            text_y = rect.y() + 30
        else:
            text_y = rect.y() + 10

        # Body text — word-wrapped
        self._set_font(p, el, el.get("font_size", 12))
        p.setPen(_c(el.get("color", "#e8e8cc")))
        body_r = QRectF(rect.x() + 12, text_y,
                        rect.width() - 24, rect.bottom() - text_y - 8)
        p.drawText(body_r, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, text)

    # ─── POMODORO TIMER ──────────────────────────────────────────────────────

    def _pomodoro(self, p, el, rect):
        """Pomodoro/countdown timer display widget."""
        import datetime as _dt
        mode      = el.get("mode", "work")        # work | break | idle
        total_s   = el.get("total_s", 25 * 60)
        remain_s  = el.get("remain_s", 25 * 60)
        running   = el.get("running", False)

        # Progress fraction
        frac = max(0.0, min(1.0, remain_s / max(total_s, 1)))
        mins = remain_s // 60
        secs = remain_s % 60

        MODE_ACCENT = {"work": "#f87171", "break": "#4ade80", "idle": "#60a5fa"}
        accent = _c(MODE_ACCENT.get(mode, "#60a5fa"))

        cx = rect.center().x()
        cy = rect.center().y()
        r  = min(rect.width(), rect.height()) / 2 - 10

        # Ring track
        pen = QPen(_c("#ffffff10"))
        pen.setWidthF(8)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Ring fill
        if frac > 0:
            pen2 = QPen(accent)
            pen2.setWidthF(8)
            pen2.setCapStyle(Qt.RoundCap)
            p.setPen(pen2)
            span = int(-frac * 360 * 16)
            p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 90 * 16, span)

        # Mode pill
        self._set_font(p, el, 9, "bold")
        p.setPen(accent)
        p.drawText(QRectF(cx - 40, cy - r - 5, 80, 14),
                   Qt.AlignCenter, mode.upper())

        # Time
        time_str = f"{mins:02d}:{secs:02d}"
        self._set_font(p, el, el.get("font_size", 28), "light")
        p.setPen(_c(el.get("color", "#ffffff")))
        p.drawText(QRectF(cx - 60, cy - 22, 120, 44), Qt.AlignCenter, time_str)

        # Status dot
        status_c = accent if running else _c("#334455")
        p.setBrush(QBrush(status_c))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy + r * 0.62), 4, 4)

    # ─── SCRIPT BUTTON ───────────────────────────────────────────────────────

    def _script_btn(self, p, el, rect):
        """Runs a command or script on click — displayed like shortcut_btn."""
        # Visually identical to shortcut_btn
        self._shortcut_btn(p, el, rect)
        # Small terminal icon overlay to distinguish
        self._set_font(p, el, 8)
        p.setPen(DS.TEXT_TERTIARY)
        p.drawText(QRectF(rect.right() - 14, rect.y() + 2, 12, 12),
                   Qt.AlignCenter, "⌘")
