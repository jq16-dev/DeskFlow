"""
plugins/spotify/plugin.py — DeskFlow Spotify Plugin.

Registers:
  - Data provider "spotify" (2s TTL)
  - Element renderer type="spotify" (patched into WidgetRenderer)
  - Templates "spotify_player" and "spotify_mini"

Auto-loaded by PluginManager. Also runnable standalone for setup:
    python plugins/spotify/plugin.py
"""

import logging
logger = logging.getLogger("DeskFlow.Plugins.Spotify")


def _spotify_player_def():
    import uuid
    def _id(): return str(uuid.uuid4())[:8]
    return {
        "name": "Spotify Now Playing",
        "position": {"x": 80, "y": 80},
        "size":     {"width": 320, "height": 160},
        "update_interval": 2000,
        "layer":    "always_on_top",
        "opacity":  1.0,
        "style": {
            "background_type": "gradient",
            "gradient_start":  "#0d0d0d",
            "gradient_end":    "#111111",
            "border_radius":   16,
            "border_width":    1,
            "border_color":    "#1db95430",
        },
        "elements": [{
            "id":              _id(),
            "type":            "spotify",
            "data_provider":   "spotify",
            "x": 0, "y": 0,   "width": 320, "height": 155,
            "show_art":        True,
            "art_size":        72,
            "show_controls":   True,
            "accent_color":    "#1db954",
            "color":           "#ffffff",
            "sub_color":       "#888888",
            "track_size":      13,
            "artist_size":     11,
            "progress_height": 4,
            "ctrl_spacing":    36,
        }]
    }


def _spotify_mini_def():
    import uuid
    def _id(): return str(uuid.uuid4())[:8]
    return {
        "name": "Spotify Mini",
        "position": {"x": 80, "y": 260},
        "size":     {"width": 300, "height": 80},
        "update_interval": 2000,
        "layer":    "always_on_top",
        "opacity":  0.95,
        "style": {
            "background_type": "glass",
            "background_color": [10, 10, 10, 200],
            "border_radius":   12,
            "border_width":    1,
            "border_color":    "#1db95425",
        },
        "elements": [{
            "id":              _id(),
            "type":            "spotify",
            "data_provider":   "spotify",
            "x": 0, "y": 0,   "width": 300, "height": 76,
            "show_art":        True,
            "art_size":        52,
            "show_controls":   False,
            "accent_color":    "#1db954",
            "color":           "#ffffff",
            "sub_color":       "#666666",
            "track_size":      12,
            "artist_size":     10,
            "progress_height": 3,
        }]
    }


def _show_setup_dialog():
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel,
        QLineEdit, QPushButton, QTextBrowser, QWidget
    )
    from PySide6.QtCore import QThread, Signal
    from PySide6.QtGui import QFont

    STYLE = """
        QDialog  { background:#0e0e14; color:#e4e4e8; font-family:'Segoe UI'; }
        QLabel   { color:#e4e4e8; }
        QLineEdit { background:#0a0a12; border:1px solid #2a2a3c; border-radius:6px;
                    padding:6px 10px; color:#e4e4e8; font-size:13px; }
        QLineEdit:focus { border-color:#1db954; }
        QPushButton { background:#1db954; color:#000; border:none;
                      padding:8px 20px; border-radius:7px; font-weight:600; }
        QPushButton:hover  { background:#1ed760; }
        QPushButton#cancel { background:#1e1e2e; color:#888; }
        QPushButton#cancel:hover { background:#252535; color:#ccc; }
        QTextBrowser { background:#070710; border:1px solid #1e1e2e;
                       border-radius:8px; padding:8px; color:#aaa; font-size:12px; }
    """

    class _AuthThread(QThread):
        done   = Signal(bool)
        status = Signal(str)
        def __init__(self, cid, sec):
            super().__init__()
            self.cid = cid; self.sec = sec
        def run(self):
            from plugins.spotify import spotify_provider as sp
            sp.CLIENT_ID     = self.cid
            sp.CLIENT_SECRET = self.sec
            self.status.emit("Browser opened — log in and authorise DeskFlow...")
            ok = sp.setup_spotify()
            self.done.emit(ok)

    dlg = QDialog()
    dlg.setWindowTitle("Connect Spotify"); dlg.resize(520, 460)
    dlg.setStyleSheet(STYLE)
    lay = QVBoxLayout(dlg); lay.setSpacing(12); lay.setContentsMargins(20,20,20,20)

    title = QLabel("🎵  Spotify Setup")
    title.setFont(QFont("Segoe UI", 16, QFont.Bold))
    lay.addWidget(title)

    info = QTextBrowser(); info.setMaximumHeight(160)
    info.setHtml("""
    <p style='color:#aaa'>Quick 4-step setup:</p>
    <ol style='color:#888; line-height:2'>
      <li>Go to <b style='color:#1db954'>developer.spotify.com/dashboard</b></li>
      <li>Click <b>Create App</b> (any name, any description)</li>
      <li>Add Redirect URI: <code style='color:#4fc3f7'>http://localhost:8888/callback</code></li>
      <li>Copy <b>Client ID</b> and <b>Client Secret</b> below, then click Connect</li>
    </ol>
    """)
    lay.addWidget(info)

    cid_edit = QLineEdit(); cid_edit.setPlaceholderText("Client ID")
    sec_edit = QLineEdit(); sec_edit.setPlaceholderText("Client Secret")
    sec_edit.setEchoMode(QLineEdit.Password)
    lay.addWidget(QLabel("Client ID")); lay.addWidget(cid_edit)
    lay.addWidget(QLabel("Client Secret")); lay.addWidget(sec_edit)

    status_lbl = QLabel(""); status_lbl.setStyleSheet("color:#555; font-size:11px;")
    lay.addWidget(status_lbl)

    row = QWidget(); rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
    cancel_btn  = QPushButton("Cancel");  cancel_btn.setObjectName("cancel")
    connect_btn = QPushButton("Connect Spotify  ▶")
    rl.addWidget(cancel_btn); rl.addWidget(connect_btn)
    lay.addWidget(row)

    cancel_btn.clicked.connect(dlg.reject)

    _t = [None]
    def _connect():
        cid = cid_edit.text().strip(); sec = sec_edit.text().strip()
        if not cid or not sec:
            status_lbl.setText("⚠  Please enter both Client ID and Secret"); return
        connect_btn.setEnabled(False)
        connect_btn.setText("Waiting for browser…")
        status_lbl.setText("Spotify login page opening in your browser")
        t = _AuthThread(cid, sec)
        t.status.connect(status_lbl.setText)
        def _done(ok):
            if ok:
                status_lbl.setText("✓  Connected! Widgets will update in ~2 seconds.")
                connect_btn.setText("✓  Done — Close")
                connect_btn.setEnabled(True)
                connect_btn.clicked.disconnect(); connect_btn.clicked.connect(dlg.accept)
            else:
                status_lbl.setText("✗  Auth failed. Check credentials and try again.")
                connect_btn.setEnabled(True); connect_btn.setText("Retry")
        t.done.connect(_done); _t[0] = t; t.start()

    connect_btn.clicked.connect(_connect)
    dlg.exec()


def register(api):
    from plugins.spotify import spotify_provider
    spotify_provider._load_tokens()
    api.register_data_provider("spotify", spotify_provider._fetch_spotify, ttl=2.0)

    from plugins.spotify import spotify_renderer
    spotify_renderer.patch_renderer()

    api.register_widget_template("spotify_player", _spotify_player_def)
    api.register_widget_template("spotify_mini",   _spotify_mini_def)

    # Attach setup dialog so editor toolbar can call it
    import plugins.spotify.spotify_provider as sp
    sp.show_setup_dialog = _show_setup_dialog

    logger.info("Spotify plugin loaded — provider + renderer + 2 templates registered")


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    _show_setup_dialog()
