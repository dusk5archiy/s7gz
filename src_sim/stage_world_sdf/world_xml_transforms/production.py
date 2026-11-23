from dataclasses import dataclass, field

from s7dcls import TransformProtocol

from lib.xml_helpers import ET
from src_sim.stage_fleet.production import ProductionFleetXmlTransform
from src_sim.stage_world_xml.magnetic_field_transforms.production import (
    ProductionMagneticFieldTransform,
)
from src_sim.stage_world_xml.physics_transforms.production import (
    ProductionPhysicsTransform,
)
from src_sim.stage_world_xml.scene_ambient_transforms.production import (
    ProductionSceneAmbientTransform,
)
from src_sim.stage_world_xml.sensors_plugin_transforms.production import (
    ProductionSensorsPluginTransform,
)
from src_sim.stage_world_xml.strip_plugins_transforms.production import (
    ProductionStripPluginsTransform,
)
from src_sim.stage_world_xml.system_plugins_transforms.production import (
    ProductionSystemPluginsTransform,
)

from .scaffold import SequentialXmlTransform


@dataclass(kw_only=True, frozen=True)
class ProductionWorldXmlTransform(TransformProtocol[ET.Element]):
    strip_plugins_transform: TransformProtocol[ET.Element] = field(
        default_factory=ProductionStripPluginsTransform
    )
    scene_ambient_transform: TransformProtocol[ET.Element] = field(
        default_factory=ProductionSceneAmbientTransform
    )
    magnetic_field_transform: TransformProtocol[ET.Element] = field(
        default_factory=ProductionMagneticFieldTransform
    )
    physics_transform: TransformProtocol[ET.Element] = field(
        default_factory=ProductionPhysicsTransform
    )
    sensors_plugin_transform: TransformProtocol[ET.Element] = field(
        default_factory=ProductionSensorsPluginTransform
    )
    system_plugins_transform: TransformProtocol[ET.Element] = field(
        default_factory=ProductionSystemPluginsTransform
    )
    fleet_transform: TransformProtocol[ET.Element] = field(
        default_factory=ProductionFleetXmlTransform
    )

    def __call__(self, x: ET.Element) -> ET.Element:
        return SequentialXmlTransform(
            transforms=(
                self.strip_plugins_transform,
                self.scene_ambient_transform,
                self.magnetic_field_transform,
                self.physics_transform,
                self.sensors_plugin_transform,
                self.system_plugins_transform,
                self.fleet_transform,
            )
        )(x)
