from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import FunctionProtocol
from src_sim.settings.resource import ResourceSettings

from ..settings.world import WorldSettings
from ..world_asset_ensurers.standard import StandardFuelUrlParser
from ..world_url_emitters.settings import Settings as WorldUrlSettings
from .scaffold import ScaffoldWorldSdfExporter
from .standard import FirstSdfLocator


@dataclass(kw_only=True, frozen=True)
class ProductionWorldSdfExporter(FunctionProtocol[Path, Path]):
    s_world: WorldSettings = field(default_factory=WorldSettings.build)
    s_url: WorldUrlSettings = field(default_factory=WorldUrlSettings.build)
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)

    def _output_path(self) -> Path:
        if self.s_world.world_url and self.s_world.world_url.strip():
            ref = StandardFuelUrlParser()(self.s_world.world_url)
            return self.s_resource.source_worlds_dir / ref.owner / f"{ref.name}.sdf"

        if self.s_world.world_name and self.s_world.world_name.strip():
            raw = self.s_world.world_name.strip()
            if "/" in raw:
                owner, name = (p.strip() for p in raw.split("/", 1))
            else:
                owner, name = self.s_url.default_owner, raw
            return self.s_resource.source_worlds_dir / owner / f"{name}.sdf"

        return self.s_resource.source_worlds_dir / "fuel_world.sdf"

    def __call__(self, x: Path) -> Path:
        return ScaffoldWorldSdfExporter(
            sdf_locator=FirstSdfLocator(),
            world_sdf_out=self._output_path(),
        )(x)
