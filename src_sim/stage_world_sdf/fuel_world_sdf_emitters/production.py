from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import EmitterProtocol, FunctionProtocol, SwallowerProtocol

from src_sim.fuel.world_asset_ensurers.production import ProductionWorldAssetEnsurer
from src_sim.fuel.world_dependency_syncers.production import (
    ProductionWorldDependencySyncer,
)
from src_sim.fuel.world_sdf_exporters.production import ProductionWorldSdfExporter
from src_sim.fuel.world_url_emitters.production import ProductionWorldUrlEmitter

from .scaffold import ScaffoldFuelWorldSdfEmitter


@dataclass(kw_only=True, frozen=True)
class ProductionFuelWorldSdfEmitter(EmitterProtocol[Path | None]):
    world_url_emitter: EmitterProtocol[str | None] = field(
        default_factory=ProductionWorldUrlEmitter
    )
    world_asset_ensurer: FunctionProtocol[str, Path] = field(
        default_factory=ProductionWorldAssetEnsurer
    )
    world_sdf_exporter: FunctionProtocol[Path, Path] = field(
        default_factory=ProductionWorldSdfExporter
    )
    dependency_syncer: SwallowerProtocol[Path] = field(
        default_factory=ProductionWorldDependencySyncer
    )

    def __call__(self) -> Path | None:
        return ScaffoldFuelWorldSdfEmitter(
            world_url_emitter=self.world_url_emitter,
            world_asset_ensurer=self.world_asset_ensurer,
            world_sdf_exporter=self.world_sdf_exporter,
            dependency_syncer=self.dependency_syncer,
        )()
