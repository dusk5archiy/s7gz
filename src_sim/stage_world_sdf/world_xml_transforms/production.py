from dataclasses import dataclass, field

from s7dcls import TransformProtocol
from lib.xml_helpers import ET
from src_sim.stage_world_xml.scene_ambient_transforms.production import (
    ProductionSceneAmbientTransform,
)

from .scaffold import SequentialXmlTransform


@dataclass(kw_only=True, frozen=True)
class ProductionWorldXmlTransform(TransformProtocol[ET.Element]):
    scene_ambient_transform: TransformProtocol[ET.Element] = field(
        default_factory=ProductionSceneAmbientTransform
    )

    def __call__(self, x):
        return SequentialXmlTransform(transforms=(self.scene_ambient_transform,))(x)
