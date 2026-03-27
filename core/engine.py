"""
DeskFlow Engine — Central widget orchestrator.
Handles standard widgets + special types: media, spotify.
"""
import logging, json, copy, uuid
from pathlib import Path
from typing import Dict, Optional, List
from PySide6.QtCore import QObject, Signal
from core.widget_instance import WidgetInstance
from utils.config import AppConfig
from utils.json_store import JsonStore

logger = logging.getLogger("DeskFlow.Engine")


def _make_special_widget(wdef: dict):
    """
    For widget_type == 'media' or 'spotify', return a special window object
    instead of a standard WidgetInstance.
    """
    wtype = wdef.get("widget_type", "")
    if wtype == "media":
        from widgets.media.media_widget import MediaWidgetWindow
        return MediaWidgetWindow(wdef)
    if wtype == "spotify":
        try:
            from plugins.spotify.spotify_widget import SpotifyWidget
            from plugins.spotify.plugin import _client
            sw = SpotifyWidget(wdef)
            if _client and _client.is_authorized:
                sw.set_client(_client)
            sw.show()
            return sw
        except Exception as e:
            logger.warning(f"Spotify widget init error: {e}")
    return None


class _SpecialInstance:
    """Wraps a special widget window to match WidgetInstance interface."""
    def __init__(self, wdef: dict, window, widget_id: str = None):
        self.widget_id  = widget_id or str(uuid.uuid4())
        self.widget_def = wdef
        self.window     = window

    def attach_to_canvas(self, canvas): self.window.show()
    def detach_from_canvas(self):
        try: self.window.stop()
        except Exception: pass
        self.window.hide(); self.window.close()

    def start_updates(self): pass
    def stop_updates(self):
        try: self.window.stop()
        except Exception: pass

    def reload(self, new_def: dict):
        self.widget_def = new_def

    def set_edit_mode(self, enabled: bool):
        try: self.window.set_edit_mode(enabled)
        except Exception: pass

    def get_current_def(self) -> dict:
        d = dict(self.widget_def)
        try:
            d["position"] = self.window.get_pos()
            d["size"]     = self.window.get_size()
        except Exception: pass
        return d


class WidgetEngine(QObject):
    widget_added   = Signal(str)
    widget_removed = Signal(str)
    widget_updated = Signal(str)
    engine_ready   = Signal()

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config   = config
        self._widgets : Dict[str, object] = {}
        self._store   = JsonStore(config.widgets_dir)

    def start(self):
        logger.info("Engine starting")
        self._load_saved()
        self.engine_ready.emit()
        logger.info(f"Engine ready — {len(self._widgets)} widgets")

    def stop(self):
        for wid in list(self._widgets):
            self._destroy(wid)
        logger.info("Engine stopped")

    def add_widget(self, wdef: dict) -> Optional[str]:
        try:
            inst = self._create_instance(wdef)
            inst.attach_to_canvas(None)
            inst.start_updates()
            self._widgets[inst.widget_id] = inst
            self._store.save(inst.widget_id, wdef)
            self.widget_added.emit(inst.widget_id)
            return inst.widget_id
        except Exception as e:
            logger.error(f"Failed to add widget: {e}", exc_info=True)
            return None

    def remove_widget(self, wid: str):
        self._destroy(wid)
        self._store.delete(wid)
        self.widget_removed.emit(wid)

    def update_widget_def(self, wid: str, wdef: dict):
        if wid not in self._widgets: return
        self._widgets[wid].reload(wdef)
        self._store.save(wid, wdef)
        self.widget_updated.emit(wid)

    def get_widget(self, wid: str): return self._widgets.get(wid)
    def get_all_widgets(self) -> List: return list(self._widgets.values())

    def get_widget_def(self, wid: str) -> Optional[dict]:
        inst = self._widgets.get(wid)
        return inst.get_current_def() if inst else self._store.load(wid)

    def set_all_edit_mode(self, enabled: bool):
        for inst in self._widgets.values():
            inst.set_edit_mode(enabled)

    def save_profile(self, name: str):
        widgets = [inst.get_current_def() for inst in self._widgets.values()]
        path = self.config.profiles_dir / f"{name}.json"
        with open(path, "w") as f:
            json.dump({"name": name, "widgets": widgets}, f, indent=2)

    def load_profile(self, name: str):
        path = self.config.profiles_dir / f"{name}.json"
        if not path.exists():
            logger.warning(f"Profile not found: {name}"); return
        with open(path) as f:
            profile = json.load(f)
        for wid in list(self._widgets):
            self._destroy(wid)
        for wdef in profile.get("widgets", []):
            self.add_widget(wdef)

    def _create_instance(self, wdef: dict, widget_id: str = None):
        wtype = wdef.get("widget_type", "")
        if wtype in ("media", "spotify"):
            win = _make_special_widget(wdef)
            if win:
                return _SpecialInstance(wdef, win, widget_id)
        inst = WidgetInstance(wdef, self.config, widget_id=widget_id)
        return inst

    def _load_saved(self):
        for wid, wdef in self._store.load_all():
            try:
                inst = self._create_instance(wdef, widget_id=wid)
                inst.attach_to_canvas(None)
                inst.start_updates()
                self._widgets[inst.widget_id] = inst
            except Exception as e:
                logger.error(f"Failed to load widget {wid}: {e}", exc_info=True)

    def _destroy(self, wid: str):
        inst = self._widgets.pop(wid, None)
        if inst:
            inst.stop_updates()
            inst.detach_from_canvas()
