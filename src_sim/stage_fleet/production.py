from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from s7dcls import TransformProtocol

from src_common.conventions.model_name import GENERATED_MODEL_PREFIX
from src_sim.settings.asset_ref import resolve_world_generated_models_dir
from src_sim.settings.resource import ResourceSettings
from src_sim.stage_vehicle.gz_model_name_transforms.production import (
    ProductionGzModelNameTransform,
)
from src_sim.stage_vehicle.production import ProductionVehicleModelBuilder
from src_sim.stage_vehicle.protocol import VehicleModelBuilderProtocol

from .fleet_planners.production import ProductionFleetPlanner
from .fleet_planners.protocol import FleetPlannerProtocol
from .protocol import FleetXmlPlacerProtocol
from .scaffold import ScaffoldFleetXmlTransform
from .settings import Settings
from .standard import StandardFleetIncludeXmlPlacer


def prune_stale_world_generated_models(
    models_dir: Path, *, keep_names: set[str]
) -> None:
    if not models_dir.is_dir():
        return
    for entry in models_dir.iterdir():
        if (
            entry.is_dir()
            and entry.name.startswith(GENERATED_MODEL_PREFIX)
            and entry.name not in keep_names
        ):
            shutil.rmtree(entry, ignore_errors=True)


@dataclass(kw_only=True, frozen=True)
class ProductionFleetXmlTransform(TransformProtocol[ET.Element]):
    world_key: str | None = None
    settings: Settings = field(default_factory=Settings.build)
    s_resource: ResourceSettings = field(default_factory=ResourceSettings.build)
    fleet_planner: FleetPlannerProtocol | None = None
    vehicle_builder: VehicleModelBuilderProtocol | None = None
    xml_placer: FleetXmlPlacerProtocol | None = None

    def __call__(self, x: ET.Element) -> ET.Element:
        cfg = self.settings.for_world(self.world_key)
        world_models_dir = resolve_world_generated_models_dir(
            self.world_key, resource=self.s_resource
        )
        if not cfg.enabled or not cfg.vehicles:
            prune_stale_world_generated_models(world_models_dir, keep_names=set())
            return x

        gz_name_transform = ProductionGzModelNameTransform()
        keep_names = {gz_name_transform(v.namespace) for v in cfg.vehicles}
        prune_stale_world_generated_models(world_models_dir, keep_names=keep_names)

        planner = self.fleet_planner or ProductionFleetPlanner(
            world_key=self.world_key,
            fleet_config=cfg,
            s_fleet=self.settings,
        )
        builder = self.vehicle_builder or ProductionVehicleModelBuilder(
            s_resource=self.s_resource,
            world_key=self.world_key,
            models_dir=world_models_dir,
        )
        runtime_root = self.s_resource.runtime_dir.resolve()
        resolved_world_models = world_models_dir.resolve()
        uri_prefix = (
            resolved_world_models.relative_to(runtime_root).as_posix()
            if resolved_world_models.is_relative_to(runtime_root)
            else None
        )
        placer = self.xml_placer or StandardFleetIncludeXmlPlacer(
            model_uri_prefix=uri_prefix,
            gz_model_name_transform=gz_name_transform,
        )
        return ScaffoldFleetXmlTransform(
            fleet_planner=planner,
            vehicle_builder=builder,
            xml_placer=placer,
        )(x)
