"""
spotify_renderer.py — Renders the Spotify now-playing element.
Patches WidgetRenderer to handle type="spotify".
Draws: album art, track/artist, progress bar, play/pause/skip controls.
"""

import io, logging, threading
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QPen, QBrush,
    QPixmap, QLinearGradient, QFont, QFontMetrics
)

logger = logging.getLogger("DeskFlow.SpotifyRenderer")

_art_cache: dict = {}
_art_lock = threading.Lock()


def _fetch_art(url: str):
    if not url or url in _art_cache:
        return
    try:
        import requests
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        px = QPixmap()
        px.loadFromData(r.content)
        if not px.isNull():
            with _art_lock:
                _art_cache[url] = px
    except Exception as e:
        logger.debug(f"Art fetch error: {e}")


def _get_art(url: str) -> Optional[QPixmap]:
    with _art_lock:
        if url in _art_cache:
            return _art_cache[url]
    threading.Thread(target=_fetch_art, args=(url,), daemon=True).start()
    return None


def _c(v, default="#ffffff") -> QColor:
    if isinstance(v, str): return QColor(v)
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        a = v[3] if len(v) == 4 else 255
        return QColor(int(v[0]), int(v[1]), int(v[2]), int(a))
    return QColor(default)


def _draw_spotify(renderer, p: QPainter, el: dict, rect: QRectF):
    eid  = el.get("id", "")
    data = renderer._cache.get(eid, {})
    if not isinstance(data, dict): data = {}

    is_playing = data.get("is_playing", False)
    track      = data.get("track",  "Not Connected")
    artist     = data.get("artist", "Set up Spotify in plugin")
    progress   = float(data.get("progress", 0))
    prog_str   = data.get("progress_str", "0:00")
    dur_str    = data.get("duration_str", "0:00")
    cover_url  = data.get("cover_url", "")
    shuffle    = data.get("shuffle", False)
    repeat     = data.get("repeat", "off")

    accent     = el.get("accent_color", "#1db954")
    text_col   = el.get("color", "#ffffff")
    sub_col    = el.get("sub_color", "#888888")
    show_art   = el.get("show_art", True)
    show_ctrl  = el.get("show_controls", True)
    art_size   = el.get("art_size", 64)
    pb_height  = el.get("progress_height", 4)

    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    # ── Album art ─────────────────────────────────────────────────────────────
    art_margin = 10
    art_x = x + art_margin
    text_x = art_x + (art_size + 12 if show_art else 0)
    text_w = w - (art_size + 22 if show_art else 20)

    if show_art:
        art_y    = y + (h - art_size) / 2
        art_rect = QRectF(art_x, art_y, art_size, art_size)
        art_path = QPainterPath()
        art_path.addRoundedRect(art_rect, 8, 8)

        pix = _get_art(cover_url) if cover_url else None
        if pix and not pix.isNull():
            p.save()
            p.setClipPath(art_path)
            scaled = pix.scaled(int(art_size), int(art_size),
                                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            cx = (scaled.width()  - int(art_size)) // 2
            cy = (scaled.height() - int(art_size)) // 2
            p.drawPixmap(int(art_rect.x()), int(art_rect.y()),
                         scaled, cx, cy, int(art_size), int(art_size))
            p.restore()
        else:
            p.fillPath(art_path, QBrush(_c("#1a1a2e")))
            p.setFont(QFont("Segoe UI", int(art_size * 0.35)))
            p.setPen(_c("#444"))
            p.drawText(art_rect, Qt.AlignCenter, "♫")

        # Playing dot
        if is_playing:
            dot = QPainterPath()
            dot.addEllipse(QPointF(art_rect.right()-5, art_rect.bottom()-5), 4, 4)
            p.fillPath(dot, QBrush(_c(accent)))

    # ── Text area ─────────────────────────────────────────────────────────────
    info_top = y + 10

    # Track name
    tf = QFont(el.get("font_family", "Segoe UI"), el.get("track_size", 13))
    tf.setWeight(QFont.DemiBold)
    p.setFont(tf); p.setPen(_c(text_col))
    fm = QFontMetrics(tf)
    p.drawText(QRectF(text_x, info_top, text_w, 20), Qt.AlignVCenter | Qt.AlignLeft,
               fm.elidedText(track, Qt.ElideRight, int(text_w)))

    # Artist
    af = QFont(el.get("font_family", "Segoe UI"), el.get("artist_size", 11))
    p.setFont(af); p.setPen(_c(sub_col))
    fm2 = QFontMetrics(af)
    p.drawText(QRectF(text_x, info_top + 22, text_w, 18), Qt.AlignVCenter | Qt.AlignLeft,
               fm2.elidedText(artist, Qt.ElideRight, int(text_w)))

    # ── Progress bar ──────────────────────────────────────────────────────────
    pb_y    = info_top + 46
    pb_rect = QRectF(text_x, pb_y, text_w, pb_height)

    tp = QPainterPath(); tp.addRoundedRect(pb_rect, pb_height/2, pb_height/2)
    p.fillPath(tp, QBrush(_c("#ffffff20")))

    if progress > 0:
        fr = QRectF(pb_rect.x(), pb_rect.y(), pb_rect.width() * progress, pb_height)
        fp = QPainterPath(); fp.addRoundedRect(fr, pb_height/2, pb_height/2)
        g  = QLinearGradient(fr.topLeft(), fr.topRight())
        g.setColorAt(0, _c(accent)); g.setColorAt(1, _c(accent))
        p.fillPath(fp, QBrush(g))
        dp = QPainterPath()
        dp.addEllipse(QPointF(fr.right(), pb_rect.center().y()), 5, 5)
        p.fillPath(dp, QBrush(_c(accent)))

    # Timestamps
    p.setFont(QFont("Segoe UI", 9)); p.setPen(_c(sub_col))
    p.drawText(QRectF(text_x, pb_y + pb_height + 2, text_w/2, 14), Qt.AlignVCenter|Qt.AlignLeft, prog_str)
    p.drawText(QRectF(text_x, pb_y + pb_height + 2, text_w, 14), Qt.AlignVCenter|Qt.AlignRight, dur_str)

    # ── Controls ──────────────────────────────────────────────────────────────
    if show_ctrl:
        ctrl_y  = pb_y + pb_height + 22
        ctrl_cx = text_x + text_w / 2
        sp      = el.get("ctrl_spacing", 34)

        buttons = [
            ("⏮", ctrl_cx - sp,  False),
            ("⏸" if is_playing else "▶", ctrl_cx, True),
            ("⏭", ctrl_cx + sp,  False),
        ]

        for icon, bx, is_main in buttons:
            br     = 18 if is_main else 14
            center = QPointF(bx, ctrl_y)
            circle = QPainterPath()
            circle.addEllipse(center, br, br)
            if is_main:
                p.fillPath(circle, QBrush(_c(accent)))
                p.setPen(_c("#000000"))
            else:
                p.fillPath(circle, QBrush(_c("#ffffff12")))
                p.setPen(_c(text_col))
            p.setFont(QFont("Segoe UI", 11 if is_main else 9))
            p.drawText(QRectF(bx-br, ctrl_y-br, br*2, br*2), Qt.AlignCenter, icon)

        # Shuffle / repeat dots
        if shuffle:
            p.setPen(_c(accent)); p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(text_x, ctrl_y-12, 24, 24), Qt.AlignCenter, "⇄")
        if repeat != "off":
            p.setPen(_c(accent)); p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(text_x+text_w-24, ctrl_y-12, 24, 24), Qt.AlignCenter, "↺")


def patch_renderer():
    """Inject 'spotify' element type into WidgetRenderer at runtime."""
    from core.renderer import WidgetRenderer
    _orig = WidgetRenderer._dispatch

    def _patched(self, p, el, w, h):
        if el.get("type") == "spotify":
            rect = QRectF(el.get("x",0), el.get("y",0), el.get("width",w), el.get("height",80))
            _draw_spotify(self, p, el, rect)
        else:
            _orig(self, p, el, w, h)

    WidgetRenderer._dispatch = _patched
    logger.info("Spotify renderer patched in")
