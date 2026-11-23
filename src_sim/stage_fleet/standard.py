from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from src_sim.stage_vehicle.gz_model_name_transforms.production import (
    ProductionGzModelNameTransform,
)
from src_sim.stage_vehicle.gz_model_name_transforms.protocol import (
    GzModelNameTransformProtocol,
)

from .models import FleetMember
from .protocol import FleetXmlPlacerProtocol


@dataclass(kw_only=True, frozen=True)
class StandardFleetIncludeXmlPlacer(FleetXmlPlacerProtocol):
    model_uri_prefix: str | None = None
    gz_model_name_transform: GzModelNameTransformProtocol = field(
        default_factory=ProductionGzModelNameTransform
    )

    def __call__(
        self, *, world: ET.Element, members: tuple[FleetMember, ...]
    ) -> ET.Element:
        prefix = self.model_uri_prefix.strip("/") if self.model_uri_prefix else ""
        for member in members:
            gz_model_name = self.gz_model_name_transform(member.vehicle.namespace)
            inc = ET.SubElement(world, "include")
            ET.SubElement(inc, "name").text = gz_model_name
            uri = (
                f"model://{prefix}/{gz_model_name}"
                if prefix
                else f"model://{gz_model_name}"
            )
            ET.SubElement(inc, "uri").text = uri
            ET.SubElement(inc, "pose").text = member.pose.to_sdf_pose_str()
        return world
