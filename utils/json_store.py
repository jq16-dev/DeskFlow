import json, logging
from pathlib import Path
from typing import Iterator, Optional, Tuple

logger = logging.getLogger("DeskFlow.Store")

class JsonStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: dict):
        with open(self.directory / f"{key}.json", "w") as f:
            json.dump(data, f, indent=2)

    def load(self, key: str) -> Optional[dict]:
        p = self.directory / f"{key}.json"
        if not p.exists(): return None
        with open(p) as f: return json.load(f)

    def delete(self, key: str):
        p = self.directory / f"{key}.json"
        if p.exists(): p.unlink()

    def load_all(self) -> Iterator[Tuple[str, dict]]:
        for p in self.directory.glob("*.json"):
            try:
                with open(p) as f:
                    yield p.stem, json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load {p}: {e}")
