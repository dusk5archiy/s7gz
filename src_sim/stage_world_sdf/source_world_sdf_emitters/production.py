from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import EmitterProtocol

from .settings import Settings


@dataclass(kw_only=True, frozen=True)
class ProductionSourceWorldSdfEmitter(EmitterProtocol[Path]):
    settings: Settings = field(default_factory=Settings.build)

    def __call__(self):
        path = self.settings.world_file or self.settings.empty_world_file
        if not path.is_file():
            raise FileNotFoundError({"path": path})

        return path
