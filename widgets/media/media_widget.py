"""
media_widget.py — Media Now Playing widget, embedded in DeskFlow canvas.

Uses WidgetInstance + WidgetWindow pattern.
No separate window. Renders via MediaRenderer.
Controls via SMTC (Windows) or title scraping fallback.
"""

import logging
import threading
from typing import Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPoint, QObject, Signal
from PySide6.QtGui import QPainter, QPaintEvent, QMouseEvent

from widgets.media import media_controller as MC
from widgets.media.media_renderer import MediaRenderer

logger = logging.getLogger("DeskFlow.MediaWidget")


class _Sig(QObject):
    updated = Signal()


class MediaWidgetWindow(QWidget):
    """
    Embedded canvas widget for media playback display.
    Integrates into DeskFlow's widget layer system.
    """

    def __init__(self, widget_def: dict, parent=None):
        super().__init__(parent)
        self.widget_def  = widget_def
        self._renderer   = MediaRenderer()
        self._state      : dict = {}
        self._hovered    : Optional[str] = None
        self._dragging   = False
        self._drag_off   = QPoint()
        self._edit_mode  = False
        self._sigs       = _Sig()
        self._sigs.updated.connect(self.update)

        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint
        layer = widget_def.get("layer", "always_on_top")
        if layer == "desktop":
            flags |= Qt.WindowStaysOnBottomHint
        elif layer == "always_on_top":
            flags |= Qt.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(True)

        pos  = widget_def.get("position", {"x": 80, "y": 400})
        size = widget_def.get("size",     {"width": 360, "height": 155})
        self.move(pos["x"], pos["y"])
        self.resize(size["width"], size["height"])
        self.setWindowOpacity(widget_def.get("opacity", 1.0))

        # Start media controller polling
        MC.start(interval=widget_def.get("update_interval", 2000) / 1000.0)  # ms → s

        # QTimer on main thread to pull state from MC and repaint
        self._timer = QTimer()
        self._timer.setInterval(max(500, widget_def.get("update_interval", 2000)))
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()

    def _tick(self):
        self._state = MC.get_state()
        self.update()

    def set_edit_mode(self, enabled: bool):
        self._edit_mode = enabled
        self.setAttribute(Qt.WA_TransparentForMouseEvents, not enabled)

    def get_pos(self):  return {"x": self.x(), "y": self.y()}
    def get_size(self): return {"width": self.width(), "height": self.height()}

    def stop(self):
        self._timer.stop()

    # ── Paint ──────────────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # Build element dict from widget_def for renderer
        el = {
            "x": 0, "y": 0,
            "width":  self.width(),
            "height": self.height(),
            "show_art":      self.widget_def.get("show_art", True),
            "show_controls": self.widget_def.get("show_controls", True),
            "font_family":   self.widget_def.get("style", {}).get("font_family", "Segoe UI"),
            "font_size":     self.widget_def.get("style", {}).get("font_size", 13),
        }

        from utils.config import AppConfig
        assets_dir = AppConfig().assets_dir

        self._renderer.paint_to_painter(
            p, self.width(), self.height(),
            self._state, el,
            hovered_btn=self._hovered,
            assets_dir=assets_dir,
        )
        p.end()

    # ── Mouse ─────────────────────────────────────────────────────────────

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._dragging:
            self.move(self.mapToGlobal(e.pos() - self._drag_off))
            return
        el = {"x": 0, "y": 0, "width": self.width(), "height": self.height(),
              "show_controls": self.widget_def.get("show_controls", True)}
        hit = self._renderer.hit_test(e.pos().x(), e.pos().y(), el)
        if hit != self._hovered:
            self._hovered = hit
            self.setCursor(Qt.PointingHandCursor if hit else Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            el = {"x": 0, "y": 0, "width": self.width(), "height": self.height(),
                  "show_controls": self.widget_def.get("show_controls", True)}
            hit = self._renderer.hit_test(e.pos().x(), e.pos().y(), el)
            if hit:
                self._handle_btn(hit)
            elif self._edit_mode:
                self._dragging = True
                self._drag_off = e.pos()

    def mouseReleaseEvent(self, e): self._dragging = False
    def leaveEvent(self, e):        self._hovered = None; self.update()

    def _handle_btn(self, btn: str):
        def _run():
            try:
                if   btn == "play":     MC.play_pause()
                elif btn == "next":     MC.next_track()
                elif btn == "prev":     MC.prev_track()
                elif btn == "vol_up":   MC.volume_up(0.05)
                elif btn == "vol_down": MC.volume_down(0.05)
                import time; time.sleep(0.3)
                self._state = MC.get_state()
                self._sigs.updated.emit()
            except Exception as ex:
                logger.debug(f"Media control error: {ex}")
        threading.Thread(target=_run, daemon=True).start()
