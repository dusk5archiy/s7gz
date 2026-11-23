from __future__ import annotations

from dataclasses import dataclass, field

from s7dcls import EmitterProtocol

from src_sim.stage_vehicle.models import VehicleSpec

from ..settings import Settings as FleetSettings


@dataclass(kw_only=True, frozen=True)
class ProductionVehicleSpecsEmitter(EmitterProtocol[tuple[VehicleSpec, ...]]):
    world_key: str | None = None
    s_fleet: FleetSettings = field(default_factory=FleetSettings.build)

    def __call__(self) -> tuple[VehicleSpec, ...]:
        return self.s_fleet.for_world(self.world_key).vehicles
