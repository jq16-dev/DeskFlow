"""
media_renderer.py — DeskFlow 2026 Media Widget Renderer.
iOS 26 premium design. Used by both:
  - MediaWidgetWindow (standalone special widget)
  - WidgetRenderer._media_now_playing() (inline canvas element)

No separate windows. Pure QPainter rendering.
"""

import logging
from pathlib import Path
from typing import Optional, Dict

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QFont, QFontMetrics,
    QLinearGradient, QRadialGradient, QPen, QBrush, QPixmap, QImage
)

logger = logging.getLogger("DeskFlow.MediaRenderer")

# ─── Source accent palette ─────────────────────────────────────────────────────

SOURCE_COLORS = {
    "spotify": "#1DB954",
    "vlc":     "#FF8C00",
    "chrome":  "#4285F4",
    "edge":    "#0078D4",
    "firefox": "#FF7139",
    "opera":   "#FF1B2D",
    "wmp":     "#00B4D8",
    "movies":  "#9B5DE5",
    "youtube": "#FF0000",
    "system":  "#60a5fa",
    "":        "#60a5fa",
}

SOURCE_LABEL = {
    "spotify": "SPOTIFY",
    "vlc":     "VLC",
    "chrome":  "CHROME",
    "edge":    "EDGE",
    "firefox": "FIREFOX",
    "wmp":     "MEDIA PLAYER",
    "movies":  "MOVIES & TV",
    "youtube": "YOUTUBE",
    "":        "MEDIA",
}

SOURCE_ICON = {
    "spotify": "♫",
    "vlc":     "▶",
    "chrome":  "●",
    "edge":    "◈",
    "firefox": "◉",
    "wmp":     "♪",
    "movies":  "▶",
    "":        "♫",
}


def _qc(v, d="#ffffff") -> QColor:
    if isinstance(v, str):
        return QColor(v)
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        return QColor(int(v[0]), int(v[1]), int(v[2]),
                      int(v[3]) if len(v) == 4 else 255)
    return QColor(d)


class MediaRenderer:
    """
    Stateful renderer — caches decoded album art pixmaps.
    Call paint_to_painter() from paintEvent or a WidgetRenderer dispatch.
    """

    def __init__(self):
        self._art_cache: Dict[str, QPixmap] = {}
        self._placeholder: Optional[QPixmap] = None

    # ── Placeholder art ──────────────────────────────────────────────────────

    def _make_placeholder(self, size: int) -> QPixmap:
        """Generate a stylish placeholder note icon."""
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)

        # Background circle with gradient
        g = QRadialGradient(size / 2, size / 2 - size * 0.1, size * 0.52)
        g.setColorAt(0, QColor(38, 38, 60))
        g.setColorAt(1, QColor(18, 18, 30))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
        p.fillPath(path, QBrush(g))

        # Music note
        p.setFont(QFont("Segoe UI", int(size * 0.38)))
        p.setPen(QColor(80, 80, 120, 160))
        p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "♫")
        p.end()
        return pix

    def _get_placeholder(self, size: int = 88) -> QPixmap:
        key = f"ph_{size}"
        if key not in self._art_cache:
            self._art_cache[key] = self._make_placeholder(size)
        return self._art_cache[key]

    def _get_art(self, art_data: Optional[bytes], art_url: str,
                 size: int = 88) -> Optional[QPixmap]:
        if not art_data:
            return None
        key = art_url or str(id(art_data))
        if key not in self._art_cache:
            img = QImage()
            if img.loadFromData(art_data):
                self._art_cache[key] = QPixmap.fromImage(img)
        return self._art_cache.get(key)

    # ── Main paint ────────────────────────────────────────────────────────────

    def paint_to_painter(self, p: QPainter, w: int, h: int,
                         state: dict, el: dict,
                         hovered_btn: Optional[str] = None,
                         assets_dir=None):

        playing   = state.get("playing", False)
        title     = state.get("title",   "") or ""
        artist    = state.get("artist",  "") or ""
        album     = state.get("album",   "") or ""
        progress  = max(0.0, min(1.0, state.get("progress", 0.0)))
        source    = state.get("source",  "")
        art_data  = state.get("art_data")
        art_url   = state.get("art_url", "")
        pos_s     = int(state.get("position_s", 0))
        dur_s     = int(state.get("duration_s", 0))
        app_name  = state.get("app_name", source.capitalize())

        show_art      = el.get("show_art", True)
        show_controls = el.get("show_controls", True)
        font_family   = el.get("font_family", "Segoe UI")
        r_corner      = el.get("border_radius", 20)

        accent    = _qc(SOURCE_COLORS.get(source, "#60a5fa"))
        label_txt = SOURCE_LABEL.get(source, "MEDIA")
        icon_txt  = SOURCE_ICON.get(source, "♫")

        rect = QRectF(el.get("x", 0), el.get("y", 0),
                      el.get("width", w), el.get("height", h))

        nothing_playing = not title

        # ── Background ───────────────────────────────────────────────────────
        p.save()
        bg_path = QPainterPath()
        bg_path.addRoundedRect(rect, r_corner, r_corner)

        # Deep glass background
        bg_g = QLinearGradient(rect.topLeft(), rect.bottomRight())
        bg_g.setColorAt(0, QColor(16, 16, 28, 235))
        bg_g.setColorAt(1, QColor(8,   8, 18, 240))
        p.fillPath(bg_path, QBrush(bg_g))

        # Top accent stripe
        stripe = QPainterPath()
        stripe.addRoundedRect(QRectF(rect.x(), rect.y(), rect.width(), 3),
                               r_corner, r_corner)
        stripe_c = QColor(accent.red(), accent.green(), accent.blue(), 140)
        p.fillPath(stripe, QBrush(stripe_c))

        # Glass top sheen
        sheen_g = QLinearGradient(rect.topLeft(), QPointF(rect.x(), rect.y() + rect.height() * 0.35))
        sheen_g.setColorAt(0, QColor(255, 255, 255, 14))
        sheen_g.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillPath(bg_path, QBrush(sheen_g))

        # Border
        p.setPen(QPen(QColor(255, 255, 255, 16), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), r_corner, r_corner)
        p.restore()

        # ── Idle state ───────────────────────────────────────────────────────
        if nothing_playing:
            p.setFont(QFont(font_family, 12))
            p.setPen(QColor(80, 80, 100))
            p.drawText(rect, Qt.AlignCenter,
                       "No media playing\nOpen Spotify, VLC, Chrome, or any media app")
            return

        # ── Album art ────────────────────────────────────────────────────────
        CTRL_H    = 40 if show_controls else 0
        BAR_H     = 20
        PADDING   = 14
        art_size  = min(int(rect.height()) - CTRL_H - BAR_H - PADDING, 88)
        art_size  = max(art_size, 36)

        if show_art:
            art_x = rect.x() + PADDING
            art_y = rect.y() + (rect.height() - CTRL_H - BAR_H - art_size) / 2 + PADDING * 0.5
            art_rect = QRectF(art_x, art_y, art_size, art_size)

            # Shadow
            sh_path = QPainterPath()
            sh_path.addRoundedRect(art_rect.adjusted(3, 4, 3, 4), 10, 10)
            p.fillPath(sh_path, QColor(0, 0, 0, 90))

            # Clip art to rounded rect
            art_clip = QPainterPath()
            art_clip.addRoundedRect(art_rect, 10, 10)
            p.setClipPath(art_clip)

            pix = self._get_art(art_data, art_url, art_size) or self._get_placeholder(art_size)
            if pix and not pix.isNull():
                scaled = pix.scaled(art_size, art_size,
                                    Qt.KeepAspectRatioByExpanding,
                                    Qt.SmoothTransformation)
                p.drawPixmap(art_rect.toRect(), scaled)
            p.setClipping(False)

            text_x  = art_x + art_size + PADDING
        else:
            text_x  = rect.x() + PADDING

        avail_w = rect.right() - text_x - PADDING

        # ── Source badge ─────────────────────────────────────────────────────
        badge_y = rect.y() + 11
        p.setFont(QFont(font_family, 9, QFont.Bold))
        p.setPen(QColor(accent.red(), accent.green(), accent.blue(), 200))
        p.drawText(QRectF(text_x, badge_y, avail_w, 14),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   f"{icon_txt}  {label_txt}")

        # ── Title ─────────────────────────────────────────────────────────────
        title_y = badge_y + 15
        f_title = QFont(font_family, el.get("font_size", 13), QFont.DemiBold)
        p.setFont(f_title)
        p.setPen(QColor(240, 242, 255))
        fm = QFontMetrics(f_title)
        p.drawText(QRectF(text_x, title_y, avail_w, 20),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   fm.elidedText(title, Qt.ElideRight, int(avail_w)))

        # ── Artist ────────────────────────────────────────────────────────────
        artist_y = title_y + 21
        f_artist = QFont(font_family, max(el.get("font_size", 13) - 2, 10))
        p.setFont(f_artist)
        p.setPen(QColor(150, 155, 175))
        fm2 = QFontMetrics(f_artist)
        p.drawText(QRectF(text_x, artist_y, avail_w, 18),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   fm2.elidedText(artist, Qt.ElideRight, int(avail_w)))

        # ── Album ─────────────────────────────────────────────────────────────
        if album and artist_y + 36 < rect.bottom() - CTRL_H - BAR_H - 10:
            album_y = artist_y + 19
            f_album = QFont(font_family, 9)
            p.setFont(f_album)
            p.setPen(QColor(80, 82, 102))
            fm3 = QFontMetrics(f_album)
            p.drawText(QRectF(text_x, album_y, avail_w, 15),
                       Qt.AlignVCenter | Qt.AlignLeft,
                       fm3.elidedText(album, Qt.ElideRight, int(avail_w)))

        # ── Progress bar ──────────────────────────────────────────────────────
        bar_margin = PADDING
        bar_bottom = rect.bottom() - (CTRL_H + 2 if show_controls else 4)
        bar_x = rect.x() + bar_margin
        bar_w = rect.width() - bar_margin * 2
        bar_h = 3.5

        # Track
        trk = QPainterPath()
        trk.addRoundedRect(QRectF(bar_x, bar_bottom - bar_h, bar_w, bar_h), 2, 2)
        p.fillPath(trk, QBrush(QColor(255, 255, 255, 20)))

        # Fill
        if progress > 0:
            fill_w = bar_w * progress
            fp = QPainterPath()
            fp.addRoundedRect(QRectF(bar_x, bar_bottom - bar_h, fill_w, bar_h), 2, 2)
            p.fillPath(fp, QBrush(accent))
            # Scrubber dot
            p.setBrush(QBrush(accent.lighter(120)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(bar_x + fill_w, bar_bottom - bar_h / 2), 5, 5)

        # Time labels
        def _fmt(s: int) -> str:
            s = max(0, s)
            return f"{s // 60}:{s % 60:02d}"

        p.setFont(QFont(font_family, 8))
        p.setPen(QColor(75, 75, 95))
        lbl_y = bar_bottom + 3
        p.drawText(QRectF(bar_x, lbl_y, 44, 12), Qt.AlignVCenter | Qt.AlignLeft,  _fmt(pos_s))
        p.drawText(QRectF(bar_x, lbl_y, bar_w, 12), Qt.AlignVCenter | Qt.AlignRight, _fmt(dur_s))

        # ── Controls ──────────────────────────────────────────────────────────
        if show_controls:
            btn_cy = int(rect.bottom() - 16)
            btn_cx = int(rect.x() + rect.width() / 2)

            BTNS = [
                ("prev", btn_cx - 40, "⏮", False),
                ("play", btn_cx,      "⏸" if playing else "▶", True),
                ("next", btn_cx + 40, "⏭", False),
            ]
            for key, bx, icon, is_play in BTNS:
                hov = hovered_btn == key
                if is_play:
                    # Play button — filled accent circle
                    c = accent.lighter(110) if hov else accent
                    p.setBrush(QBrush(c))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(QPointF(bx, btn_cy), 15, 15)
                    p.setFont(QFont(font_family, 13))
                    p.setPen(QColor("#000000"))
                else:
                    p.setFont(QFont(font_family, 15))
                    p.setPen(QColor(210, 215, 235) if hov else QColor(150, 155, 175))
                p.drawText(QRectF(bx - 15, btn_cy - 14, 30, 28), Qt.AlignCenter, icon)

        # ── Volume bar ─────────────────────────────────────────────────────────
        if el.get("show_volume", True):
            try:
                from widgets.media import media_controller as MC
                vol = MC.get_volume()
            except Exception:
                vol = -1.0

            PADDING = 14
            vol_y   = rect.bottom() - 38   # row above controls
            vol_lx  = rect.x() + PADDING
            vol_rx  = rect.right() - PADDING

            # Vol down icon
            hov_d = hovered_btn == "vol_down"
            p.setFont(QFont(font_family, 11))
            p.setPen(QColor(210, 215, 235) if hov_d else QColor(100, 102, 130))
            p.drawText(QRectF(vol_lx - 10, vol_y - 8, 20, 16), Qt.AlignCenter, "🔉")

            # Vol up icon
            hov_u = hovered_btn == "vol_up"
            p.setPen(QColor(210, 215, 235) if hov_u else QColor(100, 102, 130))
            p.drawText(QRectF(vol_rx - 10, vol_y - 8, 20, 16), Qt.AlignCenter, "🔊")

            # Volume track bar
            bar_x  = vol_lx + 18
            bar_w  = vol_rx - bar_x - 18
            bar_h  = 3.0

            trk_p = QPainterPath()
            trk_p.addRoundedRect(QRectF(bar_x, vol_y - bar_h / 2, bar_w, bar_h), 2, 2)
            p.fillPath(trk_p, QBrush(QColor(255, 255, 255, 18)))

            if vol >= 0:
                fill_w = bar_w * max(0.0, min(1.0, vol))
                if fill_w > 0:
                    fill_p = QPainterPath()
                    fill_p.addRoundedRect(QRectF(bar_x, vol_y - bar_h / 2, fill_w, bar_h), 2, 2)
                    vol_c = QLinearGradient(QPointF(bar_x, 0), QPointF(bar_x + bar_w, 0))
                    vol_c.setColorAt(0,  QColor(accent.red(), accent.green(), accent.blue(), 120))
                    vol_c.setColorAt(1,  accent)
                    p.fillPath(fill_p, QBrush(vol_c))
                    # Knob dot
                    p.setBrush(QBrush(QColor(230, 232, 255)))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(QPointF(bar_x + fill_w, vol_y), 4.5, 4.5)

    # ── Button hit test ────────────────────────────────────────────────────────

    def hit_test(self, mx: int, my: int, el: dict) -> Optional[str]:
        h = el.get("height", 130)
        x = el.get("x", 0)
        y = el.get("y", 0)
        w = el.get("width", 360)
        if not el.get("show_controls", True):
            return None

        # Playback buttons
        btn_cy = y + h - 16
        btn_cx = x + w / 2
        for key, bx, r in [("prev", btn_cx - 40, 14), ("play", btn_cx, 16), ("next", btn_cx + 40, 14)]:
            if (mx - bx) ** 2 + (my - btn_cy) ** 2 <= r ** 2:
                return key

        # Volume buttons: vol_down left, vol_up right
        PADDING = 14
        vol_y   = y + h - 38          # just above controls row
        vol_lx  = x + PADDING         # left: volume down
        vol_rx  = x + w - PADDING     # right: volume up
        if abs(my - vol_y) <= 10:
            if abs(mx - vol_lx) <= 14:
                return "vol_down"
            if abs(mx - vol_rx) <= 14:
                return "vol_up"

        return None
