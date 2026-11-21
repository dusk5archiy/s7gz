from __future__ import annotations

from dataclasses import dataclass, field

from .protocol import WorldSdfEmitterProtocol
from .settings import Settings


@dataclass(kw_only=True, frozen=True)
class ProductionWorldSdfEmitter(WorldSdfEmitterProtocol):
    settings: Settings = field(default_factory=Settings.build)

    def __call__(self):
        if self.settings.world_file is None:
            return self.settings.empty_world_file

        return self.settings.world_file
