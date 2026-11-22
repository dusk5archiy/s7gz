from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import EmitterProtocol
from src_sim.settings.gazebo import GazeboSettings
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_run.gui_config_file_emitters.production import (
    ProductionGuiConfigFileEmitter,
)
from src_sim.stage_run.world_sdf_emitters.production import ProductionWorldSdfEmitter

from .protocol import GzCommandEmitterProtocol
from .standard import StandardGzCommandBuilder


@dataclass(frozen=True, kw_only=True)
class ProductionGzCommandEmitter(GzCommandEmitterProtocol):
    s_gazebo: GazeboSettings = field(default_factory=GazeboSettings.build)
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)

    world_sdf_emitter: EmitterProtocol[Path] = field(
        default_factory=ProductionWorldSdfEmitter
    )
    gui_config_file_emitter: EmitterProtocol[Path | None] = field(
        default_factory=ProductionGuiConfigFileEmitter
    )

    def __call__(self):
        resource = self.s_resource
        settings = self.s_gazebo
        return StandardGzCommandBuilder(
            fuel_cache_dir=resource.fuel_cache_dir,
            headless=settings.headless,
            resource_paths=(
                resource.generated_models_dir,
                resource.patched_worlds_dir,
            ),
            world_sdf_emitter=self.world_sdf_emitter,
            gui_config_file_emitter=self.gui_config_file_emitter,
        )()
