from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace

from s7dcls import TransformProtocol
from src_sim.stage_vehicle.protocol import VehicleModelBuilderProtocol

from .base_station import find_base_station_pose
from .fleet_planners.production import ProductionFleetPlanner
from .fleet_planners.protocol import FleetPlannerProtocol
from .protocol import FleetXmlPlacerProtocol


@dataclass(kw_only=True, frozen=True)
class ScaffoldFleetXmlTransform(TransformProtocol[ET.Element]):
    fleet_planner: FleetPlannerProtocol
    vehicle_builder: VehicleModelBuilderProtocol
    xml_placer: FleetXmlPlacerProtocol

    def __call__(self, x: ET.Element) -> ET.Element:
        planner = self.fleet_planner
        if (
            isinstance(planner, ProductionFleetPlanner)
            and planner.base_station_pose is None
        ):
            base_station = find_base_station_pose(x)
            if base_station is not None:
                planner = replace(planner, base_station_pose=base_station)
        members = planner()
        for member in members:
            self.vehicle_builder(vehicle=member.vehicle)
        return self.xml_placer(world=x, members=members)
