from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import EmitterProtocol

from src_sim.stage_world_sdf.fuel_world_sdf_emitters.production import (
    ProductionFuelWorldSdfEmitter,
)

from .settings import Settings


@dataclass(kw_only=True, frozen=True)
class ProductionSourceWorldSdfEmitter(EmitterProtocol[Path]):
    settings: Settings = field(default_factory=Settings.build)
    fuel_world_sdf_emitter: EmitterProtocol[Path | None] = field(
        default_factory=ProductionFuelWorldSdfEmitter
    )

    def __call__(self) -> Path:
        if self.settings.world_file is not None:
            if not self.settings.world_file.is_file():
                raise FileNotFoundError({"path": self.settings.world_file})
            return self.settings.world_file

        fuel_world = self.fuel_world_sdf_emitter()
        if fuel_world is not None:
            return fuel_world

        path = self.settings.empty_world_file
        if not path.is_file():
            raise FileNotFoundError({"path": path})
        return path
