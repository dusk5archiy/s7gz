from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .protocol import OverrideStoreProtocol


@dataclass(kw_only=True, frozen=True)
class JsonFileOverrideStore(OverrideStoreProtocol):
    path: Path

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError(f"Expected JSON object in {self.path}")
        return raw

    def save(self, overrides: dict[str, Any]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(overrides, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self.path
