"""
spotify_widget.py — Interactive Spotify desktop widget.

A standalone QWidget that:
  - Polls SpotifyClient every 2 seconds
  - Fetches album art in background
  - Handles mouse clicks on controls (play/pause/prev/next)
  - Handles hover highlighting
  - Draggable in edit mode
  - Fully transparent / frameless
"""

import logging
import threading
from typing import Optional

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QTimer, QPoint, Signal, QObject
from PySide6.QtGui import QPainter, QPaintEvent, QMouseEvent, QCursor

from plugins.spotify.spotify_renderer import SpotifyWidgetRenderer

logger = logging.getLogger("DeskFlow.SpotifyWidget")


class _Signals(QObject):
    state_updated = Signal()
    art_ready     = Signal()


class SpotifyWidget(QWidget):
    """
    Self-contained Spotify Now Playing widget.
    Just instantiate, call set_client(), and show().
    """

    def __init__(self, widget_def: dict, parent=None):
        super().__init__(parent)
        self.widget_def = widget_def
        self._client    = None
        self._state     : dict = {}
        self._hovered   : Optional[str] = None
        self._dragging  = False
        self._drag_off  = QPoint()
        self._edit_mode = False
        self._renderer  = SpotifyWidgetRenderer()
        self._sigs      = _Signals()
        self._sigs.state_updated.connect(self.update)
        self._sigs.art_ready.connect(self.update)

        # Window setup
        flags = (Qt.FramelessWindowHint | Qt.Tool |
                 Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint)
        layer = widget_def.get("layer", "always_on_top")
        if layer == "desktop":
            flags = (Qt.FramelessWindowHint | Qt.Tool |
                     Qt.WindowStaysOnBottomHint | Qt.NoDropShadowWindowHint)
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

        pos  = widget_def.get("position", {"x": 80, "y": 80})
        size = widget_def.get("size",     {"width": 340, "height": 130})
        self.move(pos["x"], pos["y"])
        self.resize(size["width"], size["height"])
        self.setWindowOpacity(widget_def.get("opacity", 1.0))

        # Poll timer
        self._timer = QTimer()
        self._timer.setInterval(widget_def.get("update_interval", 2000))
        self._timer.timeout.connect(self._poll)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_client(self, client):
        self._client = client
        self._timer.start()
        self._poll()

    def stop(self):
        self._timer.stop()

    def set_edit_mode(self, enabled: bool):
        self._edit_mode = enabled
        self.setAttribute(Qt.WA_TransparentForMouseEvents, not enabled)

    def get_pos(self):  return {"x": self.x(), "y": self.y()}
    def get_size(self): return {"width": self.width(), "height": self.height()}

    # ── Polling ─────────────────────────────────────────────────────────────

    def _poll(self):
        if not self._client or not self._client.is_authorized:
            return
        def _run():
            try:
                state = self._client.get_playback_state()
                # Fetch art if changed
                art_url = state.get("art_url", "")
                if art_url and art_url not in self._renderer._art_cache:
                    art_bytes = self._client.get_album_art(art_url)
                    state["art_data"] = art_bytes
                    self._state = state
                    self._sigs.art_ready.emit()
                else:
                    state["art_data"] = None
                    self._state = state
                    self._sigs.state_updated.emit()
            except Exception as e:
                logger.debug(f"Spotify poll error: {e}")
        threading.Thread(target=_run, daemon=True).start()

    # ── Painting ────────────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        self._renderer.paint_to_painter(
            p, self.width(), self.height(),
            self._state, self._hovered)
        p.end()

    # ── Mouse events ────────────────────────────────────────────────────────

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._dragging:
            self.move(self.mapToGlobal(e.pos() - self._drag_off))
            return
        hit = self._renderer.hit_test(e.pos().x(), e.pos().y(),
                                       self.width(), self.height())
        if hit != self._hovered:
            self._hovered = hit
            self.setCursor(Qt.PointingHandCursor if hit else Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            hit = self._renderer.hit_test(
                e.pos().x(), e.pos().y(), self.width(), self.height())
            if hit and self._client:
                self._handle_button(hit)
            elif self._edit_mode:
                self._dragging = True
                self._drag_off = e.pos()

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._dragging = False

    def leaveEvent(self, e):
        self._hovered = None
        self.update()

    def _handle_button(self, btn: str):
        if not self._client: return
        def _run():
            try:
                if btn == "play":  self._client.play_pause()
                elif btn == "next": self._client.next_track()
                elif btn == "prev": self._client.prev_track()
                # Small delay then re-poll so UI updates quickly
                import time; time.sleep(0.3)
                state = self._client.get_playback_state()
                state["art_data"] = None
                self._state = state
                self._sigs.state_updated.emit()
            except Exception as e:
                logger.debug(f"Control error: {e}")
        threading.Thread(target=_run, daemon=True).start()
