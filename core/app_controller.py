"""
AppController v2 — System tray, lifecycle, and first-run wizard.
"""
import logging
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont
from PySide6.QtCore import Qt, QSize
from core.engine import WidgetEngine
from utils.config import AppConfig

logger = logging.getLogger("DeskFlow.Controller")


def _make_icon() -> QIcon:
    px = QPixmap(32, 32)
    px.fill(Qt.transparent)
    p  = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    g  = QColor("#4fc3f7")
    p.setBrush(g); p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 28, 28, 7, 7)
    p.setPen(QColor("#ffffff"))
    p.setFont(QFont("Segoe UI", 13, QFont.Bold))
    p.drawText(px.rect(), Qt.AlignCenter, "DF")
    p.end()
    return QIcon(px)


class AppController:
    def __init__(self, app: QApplication, engine: WidgetEngine, config: AppConfig):
        self.app      = app
        self.engine   = engine
        self.config   = config
        self._tray    = None
        self._editor  = None
        self._locked  = True

    def start(self):
        self.engine.start()
        self._setup_tray()
        # First run: open editor automatically
        if self.config.get("first_run", True):
            self.config.set("first_run", False)
            self._open_editor()

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(_make_icon())
        self._tray.setToolTip("DeskFlow 2026 — Widget Engine")
        menu = QMenu()

        # Open editor
        open_act = menu.addAction("🎨  Open Widget Editor")
        open_act.triggered.connect(self._open_editor)
        menu.addSeparator()

        # Lock toggle
        self._lock_act = menu.addAction("🔒  Widgets Locked")
        self._lock_act.setCheckable(True)
        self._lock_act.setChecked(True)
        self._lock_act.triggered.connect(self._toggle_lock)
        menu.addSeparator()

        # Profiles
        pm = menu.addMenu("📁  Profiles")
        for name in ["Work", "Gaming", "Minimal", "Finance"]:
            pm.addAction(name).triggered.connect(
                lambda checked=False, n=name.lower(): self.engine.load_profile(n))
        pm.addSeparator()
        pm.addAction("💾  Save Current...").triggered.connect(self._save_profile)
        menu.addSeparator()

        # Show/hide all
        menu.addAction("👁  Show All Widgets").triggered.connect(self._show_all)
        menu.addAction("🙈  Hide All Widgets").triggered.connect(self._hide_all)
        menu.addSeparator()

        # Spotify
        # Media controller
        mm = menu.addMenu("🎵  Media Widget")
        mm.addAction("Add Media Now Playing").triggered.connect(self._add_media_widget)
        mm.addAction("Add Media Compact").triggered.connect(self._add_media_compact)
        menu.addSeparator()

        sm = menu.addMenu("♫  Spotify")
        sm.addAction("Add Now Playing Widget").triggered.connect(self._add_spotify)
        sm.addAction("Setup / Re-authorize…").triggered.connect(self._spotify_setup)
        sm.addAction("Disconnect").triggered.connect(self._spotify_disconnect)
        menu.addSeparator()

        menu.addAction("❌  Quit DeskFlow").triggered.connect(self._quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activate)
        self._tray.show()
        self._tray.showMessage("DeskFlow", "DeskFlow 2026 running. Double-click to open Widget Studio.", QSystemTrayIcon.Information, 3000)

    def _toggle_lock(self, checked: bool):
        self._locked = checked
        self.engine.set_all_edit_mode(not checked)
        self._lock_act.setText("🔒  Widgets Locked" if checked else "🔓  Edit Mode Active")

    def _open_editor(self):
        from editor.editor_window import WidgetEditorWindow
        if self._editor is None or not self._editor.isVisible():
            self._editor = WidgetEditorWindow(self.engine, self.config)
            self._editor.show()
            self._editor.raise_()
        else:
            self._editor.raise_()
            self._editor.activateWindow()

    def _save_profile(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(None, "Save Profile", "Profile name:")
        if ok and name.strip():
            self.engine.save_profile(name.strip())
            self._tray.showMessage("DeskFlow", f"Profile '{name}' saved.", QSystemTrayIcon.Information, 2000)

    def _show_all(self):
        for inst in self.engine.get_all_widgets():
            inst.window.show()

    def _hide_all(self):
        for inst in self.engine.get_all_widgets():
            inst.window.hide()

    def _on_activate(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._open_editor()

    def _add_media_widget(self):
        from widgets.templates.default_widgets import media_now_playing
        wid = self.engine.add_widget(media_now_playing())
        if wid:
            self._tray.showMessage("DeskFlow", "Media Player widget added!", QSystemTrayIcon.Information, 2000)

    def _add_media_compact(self):
        from widgets.templates.default_widgets import media_compact
        wid = self.engine.add_widget(media_compact())
        if wid:
            self._tray.showMessage("DeskFlow", "Media Compact widget added!", QSystemTrayIcon.Information, 2000)

    def _add_spotify(self):
        try:
            from plugins.spotify.plugin import add_spotify_widget
            wid = add_spotify_widget(self.engine)
            if wid:
                self._tray.showMessage("DeskFlow", "Spotify widget added!", QSystemTrayIcon.Information, 2000)
            else:
                self._tray.showMessage("DeskFlow", "Spotify setup cancelled.", QSystemTrayIcon.Warning, 2000)
        except Exception as e:
            self._tray.showMessage("DeskFlow", f"Spotify error: {e}", QSystemTrayIcon.Critical, 3000)

    def _spotify_setup(self):
        try:
            from plugins.spotify.plugin import open_setup_dialog
            open_setup_dialog()
        except Exception as e:
            self._tray.showMessage("DeskFlow", f"Setup error: {e}", QSystemTrayIcon.Critical, 3000)

    def _spotify_disconnect(self):
        try:
            from plugins.spotify.plugin import disconnect
            disconnect()
            self._tray.showMessage("DeskFlow", "Spotify disconnected.", QSystemTrayIcon.Information, 2000)
        except Exception as e:
            pass

    def _quit(self):
        self.engine.stop()
        self.app.quit()
