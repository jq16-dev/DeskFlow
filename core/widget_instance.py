"""
WidgetInstance v2 — Runtime widget. 
Supports: always_on_top, desktop_layer (behind icons), normal, fullscreen_pause.
"""

import uuid, logging, os, subprocess, sys
from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF
from core.renderer import WidgetRenderer
from utils.config import AppConfig

logger = logging.getLogger("DeskFlow.Instance")



def _launch_shortcut(el: dict):
    """Launch app, URL, .lnk, file, or run command from shortcut/script btn."""
    import threading
    etype  = el.get("type", "shortcut_btn")
    target = el.get("app") or el.get("url") or el.get("path") or el.get("target") or ""
    cmd    = el.get("command") or el.get("cmd") or ""

    if etype == "script_btn" and cmd:
        # Run raw shell command
        def _run_cmd():
            try:
                subprocess.Popen(
                    cmd,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
            except Exception as e:
                logger.debug(f"Script error [{cmd}]: {e}")
        threading.Thread(target=_run_cmd, daemon=True).start()
        return

    if not target:
        return

    def _run():
        try:
            if sys.platform == "win32":
                # Use ShellExecute — handles URLs, .exe, .lnk, ms-settings:, etc.
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(None, "open", target, None, None, 1)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
        except Exception as e:
            logger.debug(f"Shortcut launch error [{target}]: {e}")
    threading.Thread(target=_run, daemon=True).start()


class WidgetWindow(QWidget):
    def __init__(self, widget_def: dict, renderer: WidgetRenderer, parent=None):
        super().__init__(parent)
        self.renderer    = renderer
        self.widget_def  = widget_def
        self._edit_mode  = False
        self._dragging   = False
        self._drag_off   = QPoint()
        self._apply_def(widget_def)

    def _apply_def(self, wd: dict):
        layer = wd.get("layer", "always_on_top")
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint

        if layer == "desktop":
            # Sit on desktop, below icons — never blocks apps
            flags |= Qt.WindowStaysOnBottomHint
        elif layer == "normal":
            pass  # normal z-order, moves with task switching
        else:   # "always_on_top" (default)
            flags |= Qt.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # locked by default

        pos  = wd.get("position", {"x": 100, "y": 100})
        size = wd.get("size",     {"width": 250, "height": 150})
        self.move(pos["x"], pos["y"])
        self.resize(size["width"], size["height"])
        self.setWindowOpacity(wd.get("opacity", 1.0))

    def reload_def(self, wd: dict):
        was_visible = self.isVisible()
        self.widget_def = wd
        self._apply_def(wd)
        if was_visible:
            self.show()

    def set_edit_mode(self, enabled: bool):
        self._edit_mode = enabled
        # Always receive mouse events (shortcut buttons work locked too)
        has_shortcuts = any(
            el.get("type") in ("shortcut_btn", "script_btn")
            for el in self.widget_def.get("elements", [])
        )
        if has_shortcuts:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        else:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, not enabled)

    def paintEvent(self, event):
        self.renderer.paint(self, event)

    def _hit_shortcut(self, pos):
        """Return element dict if a shortcut_btn or script_btn was clicked."""
        elements = self.widget_def.get("elements", [])
        for el in reversed(elements):
            if el.get("type") not in ("shortcut_btn", "script_btn"):
                continue
            r = QRectF(el.get("x", 0), el.get("y", 0),
                       el.get("width", 80), el.get("height", 50))
            if r.contains(pos.x(), pos.y()):
                return el
        return None

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            el = self._hit_shortcut(e.pos())
            if el:
                _launch_shortcut(el)
                return
        if self._edit_mode and e.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_off = e.pos()

    def mouseMoveEvent(self, e):
        if self._dragging:
            self.move(self.mapToGlobal(e.pos() - self._drag_off))

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def get_pos(self):  return {"x": self.x(), "y": self.y()}
    def get_size(self): return {"width": self.width(), "height": self.height()}


class WidgetInstance:
    def __init__(self, widget_def: dict, config: AppConfig, widget_id: Optional[str] = None):
        self.widget_id  = widget_id or str(uuid.uuid4())
        self.widget_def = widget_def
        self.config     = config
        self._timer: Optional[QTimer] = None
        self.renderer   = WidgetRenderer(widget_def, config)
        self.window     = WidgetWindow(widget_def, self.renderer)

    def attach_to_canvas(self, canvas):
        self.window.show()

    def detach_from_canvas(self):
        self.window.hide()
        self.window.close()

    def start_updates(self):
        interval = int(self.widget_def.get("update_interval", 1000))
        self._timer = QTimer()
        self._timer.setInterval(max(100, interval))
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()

    def stop_updates(self):
        if self._timer:
            self._timer.stop()
            self._timer = None

    def reload(self, new_def: dict):
        self.widget_def = new_def
        self.stop_updates()
        self.renderer.reload(new_def)
        self.window.reload_def(new_def)
        self.start_updates()

    def set_edit_mode(self, enabled: bool):
        self.window.set_edit_mode(enabled)

    def get_current_def(self) -> dict:
        d = dict(self.widget_def)
        d["position"] = self.window.get_pos()
        d["size"]     = self.window.get_size()
        return d

    def _tick(self):
        self.renderer.refresh_data()
        self.window.update()
