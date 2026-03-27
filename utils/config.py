"""
AppConfig — Central configuration and persistent settings.
"""

import json
import os
from pathlib import Path


class AppConfig:
    def __init__(self):
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", Path.home())) / "DeskFlow"
        else:
            base = Path.home() / ".config" / "DeskFlow"

        self.app_dir      = base
        self.widgets_dir  = base / "widgets"
        self.themes_dir   = base / "themes"
        self.plugins_dir  = base / "plugins"
        self.profiles_dir = base / "profiles"
        self.assets_dir   = Path(__file__).parent.parent / "assets"

        for d in [self.widgets_dir, self.themes_dir,
                  self.plugins_dir, self.profiles_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self._path = base / "settings.json"
        self._settings = {}
        if self._path.exists():
            try:
                with open(self._path) as f:
                    self._settings = json.load(f)
            except Exception:
                pass

    def get(self, key, default=None):
        return self._settings.get(key, default)

    def set(self, key, value):
        self._settings[key] = value
        self._save()

    def _save(self):
        with open(self._path, "w") as f:
            json.dump(self._settings, f, indent=2)
