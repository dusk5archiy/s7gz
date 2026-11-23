from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src_host.settings.common import CommonSettings

from .protocol import OverrideStoreProtocol
from .standard import JsonFileOverrideStore


@dataclass(kw_only=True, frozen=True)
class ProductionOverrideStore(OverrideStoreProtocol):
    s_common: CommonSettings = field(default_factory=CommonSettings.build)

    def _delegate(self) -> JsonFileOverrideStore:
        return JsonFileOverrideStore(path=self.s_common.ui_json_file)

    def load(self) -> dict[str, Any]:
        return self._delegate().load()

    def save(self, overrides: dict[str, Any]) -> Path:
        return self._delegate().save(overrides)
