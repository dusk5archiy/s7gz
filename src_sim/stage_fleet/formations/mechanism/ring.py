from __future__ import annotations

import math
from dataclasses import dataclass

from ...models import GeoPose
from ..protocol import FormationProtocol


def compute_ring_radius(*, count: int, spacing_m: float) -> float:
    if count <= 1:
        return 0.0
    return spacing_m / (2.0 * math.sin(math.pi / count))


@dataclass(kw_only=True, frozen=True)
class RingFormation(FormationProtocol):
    radius_m: float = 3.0
    min_separation_m: float = 1.0

    def poses(
        self,
        *,
        center: GeoPose,
        count: int,
    ) -> tuple[GeoPose, ...]:
        if count <= 0:
            return ()
        if count == 1:
            return (center,)
        chord_m = 2.0 * self.radius_m * math.sin(math.pi / count)
        if chord_m + 1e-9 < self.min_separation_m:
            raise ValueError(
                f"{count} vehicles on ring radius {self.radius_m:.2f} m are {chord_m:.2f} m apart, "
                f"below min_separation_m ({self.min_separation_m:.2f} m)"
            )
        phase_rad = math.radians(center.yaw_deg)
        return tuple(
            GeoPose(
                east_m=center.east_m
                + self.radius_m * math.cos(phase_rad + 2.0 * math.pi * i / count),
                north_m=center.north_m
                + self.radius_m * math.sin(phase_rad + 2.0 * math.pi * i / count),
                up_m=center.up_m,
                roll_deg=center.roll_deg,
                pitch_deg=center.pitch_deg,
                yaw_deg=center.yaw_deg,
            )
            for i in range(count)
        )


__all__ = ["RingFormation", "compute_ring_radius"]
