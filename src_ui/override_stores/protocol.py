from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class OverrideStoreProtocol(Protocol):
    def load(self) -> dict[str, Any]: ...

    def save(self, overrides: dict[str, Any]) -> Path: ...
