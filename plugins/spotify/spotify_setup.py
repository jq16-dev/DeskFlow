"""
spotify_setup.py — Setup wizard for Spotify OAuth.

Guides the user through:
  1. Creating a Spotify Developer app (with link + instructions)
  2. Entering their Client ID
  3. Clicking Authorize (opens browser)
  4. Confirming success
"""

import json
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QColor, QDesktopServices, QIcon
from PySide6.QtCore import QUrl

logger = logging.getLogger("DeskFlow.SpotifySetup")

SETUP_STYLE = """
* { font-family: 'Segoe UI'; font-size: 13px; color: #e4e4e8; }
QDialog { background: #0e0e16; }
QWidget { background: transparent; }
QLineEdit {
    background: #0a0a14;
    border: 1px solid #2a2a40;
    border-radius: 7px;
    padding: 8px 12px;
    color: #e4e4e8;
    font-size: 13px;
}
QLineEdit:focus { border-color: #1DB954; }
QPushButton {
    background: #1e1e2e;
    border: 1px solid #2a2a3e;
    border-radius: 7px;
    padding: 8px 20px;
    font-size: 13px;
}
QPushButton:hover { background: #252538; border-color: #1DB954; }
QPushButton#spotify {
    background: #1DB954;
    border: none;
    color: #000;
    font-weight: bold;
    font-size: 14px;
    padding: 10px 28px;
}
QPushButton#spotify:hover { background: #1ed760; }
QPushButton#spotify:disabled { background: #1a4a2a; color: #666; }
QLabel#title { font-size: 20px; font-weight: 700; color: #1DB954; }
QLabel#step  { font-size: 11px; font-weight: 700; color: #555; letter-spacing: 2px; }
QFrame#card  { background: #13131e; border: 1px solid #1e1e2e; border-radius: 10px; padding: 12px; }
QLabel#success { font-size: 15px; color: #1DB954; font-weight: 600; }
QLabel#error   { font-size: 12px; color: #ef5350; }
"""

INSTRUCTIONS = """
<html><body style="font-family:Segoe UI;font-size:12px;color:#aaa;line-height:1.7">
<b style="color:#1DB954">Step 1 — Create a free Spotify Developer App:</b><br>
1. Go to <a href="https://developer.spotify.com/dashboard" style="color:#1DB954">developer.spotify.com/dashboard</a><br>
2. Click <b>Create App</b><br>
3. App name: <i>DeskFlow</i> (anything works)<br>
4. Redirect URI: <code style="background:#1a1a2a;padding:2px 6px;border-radius:3px">http://localhost:8765/callback</code><br>
5. Check <b>Web API</b> and save<br>
6. Copy your <b>Client ID</b> from the app settings page<br><br>
<b style="color:#1DB954">Step 2 — Paste Client ID below and click Authorize</b><br>
Your browser will open Spotify's login. After approving, come back here.
</body></html>
"""


class _AuthWorker(QObject):
    success = Signal()
    failed  = Signal(str)

    def __init__(self, client):
        super().__init__()
        self._client = client

    def run(self):
        try:
            ok = self._client.authorize()
            if ok: self.success.emit()
            else:  self.failed.emit("Authorization was cancelled or timed out.")
        except Exception as e:
            self.failed.emit(str(e))


class SpotifySetupDialog(QDialog):

    def __init__(self, client_id_path: Path, parent=None):
        super().__init__(parent)
        self.client_id_path = client_id_path
        self._client        = None
        self._worker        = None
        self._thread        = None
        self._authorized    = False

        self.setWindowTitle("Spotify Setup — DeskFlow")
        self.setFixedSize(520, 560)
        self.setStyleSheet(SETUP_STYLE)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build()
        self._load_saved_id()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(28, 28, 28, 28); lay.setSpacing(16)

        # Title
        title = QLabel("♫  Spotify Integration"); title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter); lay.addWidget(title)

        # Instructions card
        card = QFrame(); card.setObjectName("card")
        cl = QVBoxLayout(card); cl.setContentsMargins(12,12,12,12)
        inst = QLabel(INSTRUCTIONS); inst.setWordWrap(True)
        inst.setOpenExternalLinks(True); cl.addWidget(inst)
        lay.addWidget(card)

        # Client ID input
        step1 = QLabel("CLIENT ID"); step1.setObjectName("step"); lay.addWidget(step1)
        self._cid_edit = QLineEdit()
        self._cid_edit.setPlaceholderText("Paste your Spotify Client ID here…")
        lay.addWidget(self._cid_edit)

        # Open dashboard button
        dash_btn = QPushButton("🌐  Open Spotify Developer Dashboard")
        dash_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://developer.spotify.com/dashboard")))
        lay.addWidget(dash_btn)

        # Authorize button
        self._auth_btn = QPushButton("✓  Authorize with Spotify")
        self._auth_btn.setObjectName("spotify")
        self._auth_btn.clicked.connect(self._start_auth)
        lay.addWidget(self._auth_btn)

        # Status label
        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setWordWrap(True)
        lay.addWidget(self._status)

        lay.addStretch()

        # Bottom buttons
        btns = QHBoxLayout()
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.reject)
        btns.addStretch(); btns.addWidget(self._close_btn)
        lay.addLayout(btns)

    def _load_saved_id(self):
        if self.client_id_path.exists():
            try:
                data = json.loads(self.client_id_path.read_text())
                cid  = data.get("client_id", "")
                if cid: self._cid_edit.setText(cid)
            except Exception: pass

    def _save_client_id(self, cid: str):
        self.client_id_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if self.client_id_path.exists():
            try: data = json.loads(self.client_id_path.read_text())
            except Exception: pass
        data["client_id"] = cid
        self.client_id_path.write_text(json.dumps(data))

    def _start_auth(self):
        cid = self._cid_edit.text().strip()
        if not cid:
            self._set_error("Please paste your Client ID first.")
            return

        self._save_client_id(cid)

        from plugins.spotify.spotify_client import SpotifyClient
        self._client = SpotifyClient(cid)

        self._auth_btn.setEnabled(False)
        self._auth_btn.setText("⏳  Waiting for browser authorization…")
        self._status.setText("")

        self._worker = _AuthWorker(self._client)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.success.connect(self._on_success)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _on_success(self):
        self._authorized = True
        self._auth_btn.setText("✓  Connected!")
        self._auth_btn.setEnabled(False)
        self._status.setObjectName("success")
        self._status.setText("✓  Spotify connected successfully! You can close this dialog.")
        self._status.setStyleSheet("color:#1DB954;font-size:14px;font-weight:600;")
        self._close_btn.setText("Done")
        self._close_btn.clicked.disconnect()
        self._close_btn.clicked.connect(self.accept)
        if self._thread: self._thread.quit()

    def _on_failed(self, msg: str):
        self._auth_btn.setEnabled(True)
        self._auth_btn.setText("✓  Authorize with Spotify")
        self._set_error(f"Authorization failed: {msg}")
        if self._thread: self._thread.quit()

    def _set_error(self, msg: str):
        self._status.setText(msg)
        self._status.setStyleSheet("color:#ef5350;font-size:12px;")

    @property
    def authorized_client(self):
        return self._client if self._authorized else None
