from __future__ import annotations

from dataclasses import dataclass, field

from s7dcls import EmitterProtocol

from src_sim.stage_vehicle.models import VehicleSpec

from ..formations.protocol import FormationProtocol
from ..models import FleetMember, GeoPose
from .protocol import FleetPlannerProtocol


@dataclass(kw_only=True, frozen=True)
class StandardFleetPlanner(FleetPlannerProtocol):
    vehicle_specs_emitter: EmitterProtocol[tuple[VehicleSpec, ...]]
    formation: FormationProtocol
    center: GeoPose
    pose_overrides: dict[str, GeoPose] = field(default_factory=dict)

    def __call__(self) -> tuple[FleetMember, ...]:
        vehicles = self.vehicle_specs_emitter()
        poses = self.formation.poses(
            center=self.center,
            count=len(vehicles),
        )
        return tuple(
            FleetMember(
                index=idx,
                vehicle=vehicle,
                pose=self.pose_overrides.get(vehicle.namespace, pose),
            )
            for idx, (vehicle, pose) in enumerate(zip(vehicles, poses, strict=True))
        )
