from __future__ import annotations

import math
from dataclasses import dataclass

from ...models import GeoPose
from ..protocol import FormationProtocol


@dataclass(kw_only=True, frozen=True)
class LineAbreastFormation(FormationProtocol):
    spacing_m: float = 2.5
    min_separation_m: float = 1.0

    def poses(
        self,
        *,
        center: GeoPose,
        count: int,
    ) -> tuple[GeoPose, ...]:
        if count > 1 and self.spacing_m < self.min_separation_m:
            raise ValueError(
                f"line_abreast spacing_m ({self.spacing_m} m) is below min_separation_m ({self.min_separation_m} m)"
            )
        yaw_rad = math.radians(center.yaw_deg)
        left_east = -math.sin(yaw_rad)
        left_north = math.cos(yaw_rad)
        return tuple(
            GeoPose(
                east_m=center.east_m
                + left_east * (count - 1 - 2 * i) * self.spacing_m / 2.0,
                north_m=center.north_m
                + left_north * (count - 1 - 2 * i) * self.spacing_m / 2.0,
                up_m=center.up_m,
                roll_deg=center.roll_deg,
                pitch_deg=center.pitch_deg,
                yaw_deg=center.yaw_deg,
            )
            for i in range(count)
        )


__all__ = ["LineAbreastFormation"]
