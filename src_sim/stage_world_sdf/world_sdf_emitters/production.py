from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lib.type_emitters.protocol import EmitterProtocol, TransformProtocol
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_world_sdf.world_text_transforms.production import (
    ProductionWorldTextTransform,
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
    world_text_transform: TransformProtocol[str] = field(
        default_factory=ProductionWorldTextTransform
    )

    def __call__(self):
        return ScaffoldWorldSdfEmitter(
            source_world_emitter=self.source_world_emitter,
            world_text_transformd=self.world_text_transform,
            patched_worlds_dir=self.s_resource.patched_worlds_dir,
        )()


__all__ = ["ProductionWorldSdfEmitter"]
