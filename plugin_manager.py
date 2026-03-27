import logging, importlib.util, sys
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("DeskFlow.Plugins")

class PluginAPI:
    def register_data_provider(self, key, fn, ttl=1.0):
        from core.data_providers import DataProviderRegistry
        DataProviderRegistry.register(key, fn, ttl)
        logger.info(f"Plugin registered provider: {key}")

    def register_widget_template(self, key, fn):
        from widgets.templates.default_widgets import TEMPLATES
        TEMPLATES[key] = fn

class PluginManager:
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir
        self._api = PluginAPI()

    def load_all(self):
        if not self.plugins_dir.exists(): return
        for path in self.plugins_dir.glob("*/plugin.py"):
            name = path.parent.name
            try:
                spec = importlib.util.spec_from_file_location(f"plugins.{name}", path)
                mod  = importlib.util.module_from_spec(spec)
                sys.modules[f"plugins.{name}"] = mod
                spec.loader.exec_module(mod)
                if hasattr(mod, "register"): mod.register(self._api)
                logger.info(f"Plugin loaded: {name}")
            except Exception as e:
                logger.error(f"Plugin load failed [{name}]: {e}", exc_info=True)
