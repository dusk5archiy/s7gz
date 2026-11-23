from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from s7dcls import TransformProtocol

from src_sim.stage_vehicle.production import ProductionVehicleModelBuilder
from src_sim.stage_vehicle.protocol import VehicleModelBuilderProtocol

from .fleet_planners.production import ProductionFleetPlanner
from .fleet_planners.protocol import FleetPlannerProtocol
from .protocol import FleetXmlPlacerProtocol
from .scaffold import ScaffoldFleetXmlTransform
from .settings import Settings
from .standard import StandardFleetIncludeXmlPlacer


@dataclass(kw_only=True, frozen=True)
class ProductionFleetXmlTransform(TransformProtocol[ET.Element]):
    world_key: str | None = None
    settings: Settings = field(default_factory=Settings.build)
    fleet_planner: FleetPlannerProtocol | None = None
    vehicle_builder: VehicleModelBuilderProtocol = field(
        default_factory=ProductionVehicleModelBuilder
    )
    xml_placer: FleetXmlPlacerProtocol = field(
        default_factory=StandardFleetIncludeXmlPlacer
    )

    def __call__(self, x: ET.Element) -> ET.Element:
        cfg = self.settings.for_world(self.world_key)
        if not cfg.enabled or not cfg.vehicles:
            return x

        planner = self.fleet_planner or ProductionFleetPlanner(
            world_key=self.world_key,
            fleet_config=cfg,
            s_fleet=self.settings,
        )
        return ScaffoldFleetXmlTransform(
            fleet_planner=planner,
            vehicle_builder=self.vehicle_builder,
            xml_placer=self.xml_placer,
        )(x)
