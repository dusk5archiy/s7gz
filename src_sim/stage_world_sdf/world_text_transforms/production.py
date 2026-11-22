from dataclasses import dataclass, field

from s7dcls import TransformProtocol
from lib.xml_helpers import ET
from src_sim.stage_world_sdf.world_xml_transforms.production import (
    ProductionWorldXmlTransform,
)

from .protocol import WorldTextTransformProtocol
from .scaffold import ScaffoldWorldTextTransform


@dataclass(kw_only=True, frozen=True)
class ProductionWorldTextTransform(WorldTextTransformProtocol):
    world_transform: TransformProtocol[ET.Element] = field(
        default_factory=ProductionWorldXmlTransform
    )

    def __call__(self, text):
        return ScaffoldWorldTextTransform(
            world_transform=self.world_transform,
        )(text)
