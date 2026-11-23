from __future__ import annotations

import math
from dataclasses import dataclass

from src_sim.stage_vehicle.models import VehicleSpec


@dataclass(kw_only=True, frozen=True)
class GeoPose:
    """World ENU pose (meters and degrees) converted to SDF `<pose>`."""

    east_m: float = 0.0
    north_m: float = 0.0
    up_m: float = 0.0
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0

    def to_sdf_pose_str(self) -> str:
        return (
            f"{self.east_m:g} {self.north_m:g} {self.up_m:g} "
            f"{math.radians(self.roll_deg):g} "
            f"{math.radians(self.pitch_deg):g} "
            f"{math.radians(self.yaw_deg):g}"
        )


@dataclass(kw_only=True, frozen=True)
class FleetMember:
    index: int
    vehicle: VehicleSpec
    pose: GeoPose
