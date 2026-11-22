from dataclasses import dataclass, field

from s7dcls import SequenceTransform, TransformProtocol

from lib.xml_helpers import ET
from src_sim.fuel.ignition_plugin_transforms import IgnitionPluginTransform
from src_sim.fuel.uri_localizers.production import ProductionFuelUriLocalizer
from src_sim.stage_world_sdf.world_xml_transforms.production import (
    ProductionWorldXmlTransform,
)

from .protocol import WorldTextTransformProtocol
from .scaffold import ScaffoldWorldTextTransform


@dataclass(kw_only=True, frozen=True)
class ProductionWorldTextTransform(WorldTextTransformProtocol):
    fuel_text_localizer: TransformProtocol[str] = field(
        default_factory=ProductionFuelUriLocalizer
    )
    ignition_plugin_transform: TransformProtocol[str] = field(
        default_factory=IgnitionPluginTransform
    )
    world_transform: TransformProtocol[ET.Element] = field(
        default_factory=ProductionWorldXmlTransform
    )

    def __call__(self, text: str) -> str:
        return ScaffoldWorldTextTransform(
            text_transform=SequenceTransform(
                transforms=[self.fuel_text_localizer, self.ignition_plugin_transform]
            ),
            world_transform=self.world_transform,
        )(text)
