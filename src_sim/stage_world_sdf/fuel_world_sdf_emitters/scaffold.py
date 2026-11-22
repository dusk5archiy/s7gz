from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from s7dcls import EmitterProtocol, FunctionProtocol, SwallowerProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldFuelWorldSdfEmitter(EmitterProtocol[Path | None]):
    world_url_emitter: EmitterProtocol[str | None]
    world_asset_ensurer: FunctionProtocol[str, Path]
    world_sdf_exporter: FunctionProtocol[Path, Path]
    dependency_syncer: SwallowerProtocol[Path]

    def __call__(self) -> Path | None:
        world_url = self.world_url_emitter()
        if world_url is None:
            return None

        world_dir = self.world_asset_ensurer(world_url)
        world_sdf = self.world_sdf_exporter(world_dir)
        self.dependency_syncer(world_sdf)
        return world_sdf
