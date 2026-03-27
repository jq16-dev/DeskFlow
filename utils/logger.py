import logging, sys
from pathlib import Path

def setup_logger(level=logging.INFO):
    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s", "%H:%M:%S")
    root = logging.getLogger("DeskFlow")
    root.setLevel(level)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)
    try:
        lp = Path.home() / ".config" / "DeskFlow"
        lp.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(lp / "app.log", encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception:
        pass
