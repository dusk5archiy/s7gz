from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import EmitterProtocol, TransformProtocol

from src_sim.fuel.patched_models import sync_world_models_to_patched
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_fleet.production import ProductionFleetXmlTransform
from src_sim.stage_fleet.settings import resolve_world_fleet_key
from src_sim.stage_world_sdf.world_text_transforms.production import (
    ProductionWorldTextTransform,
)
from src_sim.stage_world_sdf.world_xml_transforms.production import (
    ProductionWorldXmlTransform,
)

from ..source_world_sdf_emitters.production import (
    ProductionSourceWorldSdfEmitter,
)
from .scaffold import ScaffoldWorldSdfEmitter


@dataclass(kw_only=True, frozen=True)
class ProductionWorldSdfEmitter(EmitterProtocol[Path]):
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)
    source_world_emitter: EmitterProtocol[Path] = field(
        default_factory=ProductionSourceWorldSdfEmitter
    )
    world_text_transform: TransformProtocol[str] | None = None

    def __call__(self):
        source_file = self.source_world_emitter()
        world_key = resolve_world_fleet_key(source_file, resource=self.s_resource)
        text_transform = self.world_text_transform or ProductionWorldTextTransform(
            world_transform=ProductionWorldXmlTransform(
                fleet_transform=ProductionFleetXmlTransform(world_key=world_key)
            )
        )
        out_sdf = ScaffoldWorldSdfEmitter(
            source_world_emitter=lambda: source_file,
            world_text_transformd=text_transform,
            patched_worlds_dir=self.s_resource.patched_worlds_dir,
            source_worlds_dir=self.s_resource.source_worlds_dir,
        )()
        sync_world_models_to_patched([out_sdf], resource=self.s_resource)
        return out_sdf


__all__ = ["ProductionWorldSdfEmitter"]
