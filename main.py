"""
DeskFlow 2026 — Windows Desktop Widget Engine
The Rainmeter Killer. Modern. Fast. Beautiful.
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QFont

from core.engine import WidgetEngine
from core.app_controller import AppController
from utils.config import AppConfig
from utils.logger import setup_logger
import logging


def main():
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("DeskFlow")
    app.setApplicationVersion("2026.1")
    app.setOrganizationName("DeskFlow")
    app.setQuitOnLastWindowClosed(False)

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    setup_logger()
    logger = logging.getLogger("DeskFlow")
    logger.info("DeskFlow 2026 starting")

    config = AppConfig()
    engine = WidgetEngine(config)

    # Auto-load plugins
    from plugin_manager import PluginManager
    pm = PluginManager(config.plugins_dir)
    pm.load_all()

    controller = AppController(app, engine, config)
    controller.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
